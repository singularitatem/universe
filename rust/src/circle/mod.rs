pub mod types;

use anyhow::{bail, Result};
use reqwest::Client;
use tracing::debug;

use crate::{config::Config, eip3009::TransferAuth};
use types::{CreatePaymentRequest, CreatePaymentResponse, GetPaymentResponse, PaymentData};

pub struct CircleClient {
    client: Client,
    api_key: String,
    api_url: String,
}

impl CircleClient {
    pub fn new(config: &Config) -> Self {
        Self {
            client: Client::new(),
            api_key: config.circle_api_key.clone(),
            api_url: config.circle_api_url.clone(),
        }
    }

    pub async fn create_payment(
        &self,
        chain: &str,
        authorization: TransferAuth,
    ) -> Result<PaymentData> {
        let url = format!("{}/v1/gateway/payments", self.api_url);
        let body = CreatePaymentRequest {
            chain: chain.to_string(),
            authorization,
        };

        debug!("POST {url}");
        let resp = self
            .client
            .post(&url)
            .bearer_auth(&self.api_key)
            .json(&body)
            .send()
            .await?;

        if !resp.status().is_success() {
            let status = resp.status();
            let text = resp.text().await.unwrap_or_default();
            bail!("Circle API error {status}: {text}");
        }

        let parsed: CreatePaymentResponse = resp.json().await?;
        Ok(parsed.data)
    }

    pub async fn get_payment(&self, payment_id: &str) -> Result<PaymentData> {
        let url = format!("{}/v1/gateway/payments/{payment_id}", self.api_url);
        debug!("GET {url}");

        let resp = self
            .client
            .get(&url)
            .bearer_auth(&self.api_key)
            .send()
            .await?;

        if !resp.status().is_success() {
            let status = resp.status();
            let text = resp.text().await.unwrap_or_default();
            bail!("Circle API error {status}: {text}");
        }

        let parsed: GetPaymentResponse = resp.json().await?;
        Ok(parsed.data)
    }
}
