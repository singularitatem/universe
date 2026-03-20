use alloy::primitives::{Address, U256};
use anyhow::{bail, Result};
use reqwest::{Client, StatusCode};
use serde_json::Value;
use tracing::info;

use crate::{circle::CircleClient, config::Config, wallet::Wallet};

pub struct PaymentClient {
    http: Client,
    wallet: Wallet,
    config: Config,
    circle: CircleClient,
}

impl PaymentClient {
    pub fn new(wallet: Wallet, config: Config) -> Self {
        let circle = CircleClient::new(&config);
        Self {
            http: Client::new(),
            wallet,
            config,
            circle,
        }
    }

    /// Perform an x402-aware GET: auto-pay on 402.
    pub async fn get_with_payment(&self, url: &str) -> Result<Value> {
        info!("GET {url}");
        let resp = self.http.get(url).send().await?;

        if resp.status() != StatusCode::PAYMENT_REQUIRED {
            let body: Value = resp.json().await?;
            return Ok(body);
        }

        // Parse x402 requirements from header or body
        let payment_info: Value = if let Some(h) = resp.headers().get("x-payment-required") {
            serde_json::from_str(h.to_str().unwrap_or("{}"))?
        } else {
            resp.json().await?
        };

        let accepts = payment_info["accepts"]
            .as_array()
            .and_then(|a| a.first())
            .cloned()
            .unwrap_or_default();

        let pay_to: Address = accepts["payTo"]
            .as_str()
            .unwrap_or(&self.config.circle_gateway)
            .parse()
            .unwrap_or_else(|_| self.config.circle_gateway.parse().unwrap());

        let amount = accepts["maxAmountRequired"]
            .as_str()
            .unwrap_or("1")
            .parse::<u64>()
            .unwrap_or(self.config.payment_amount);

        info!("Signing EIP-3009 authorization: {amount} USDC units → {pay_to:#x}");
        let auth = self
            .wallet
            .sign_transfer(pay_to, U256::from(amount), &self.config)
            .await?;

        // Submit to Circle
        let chain = format!("base-sepolia");
        let payment = self.circle.create_payment(&chain, auth.clone()).await?;
        info!("Payment submitted: {} (status: {})", payment.id, payment.status);

        // Retry request with X-Payment header
        let auth_json = serde_json::to_string(&auth)?;
        info!("Retrying GET {url} with X-Payment header");
        let retry = self
            .http
            .get(url)
            .header("x-payment", &auth_json)
            .send()
            .await?;

        if !retry.status().is_success() {
            let status = retry.status();
            let text = retry.text().await.unwrap_or_default();
            bail!("Request failed after payment ({status}): {text}");
        }

        let body: Value = retry.json().await?;
        Ok(body)
    }
}
