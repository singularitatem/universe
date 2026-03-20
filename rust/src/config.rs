use anyhow::Result;
use std::env;

#[derive(Debug, Clone)]
pub struct Config {
    pub private_key: String,
    pub circle_api_key: String,
    pub chain_id: u64,
    pub usdc_address: String,
    pub circle_gateway: String,
    pub circle_api_url: String,
    pub server_port: u16,
    pub payment_amount: u64,
}

impl Config {
    pub fn from_env() -> Result<Self> {
        dotenvy::dotenv().ok();
        Ok(Config {
            private_key: env::var("PRIVATE_KEY")
                .unwrap_or_else(|_| "0x0000000000000000000000000000000000000000000000000000000000000001".into()),
            circle_api_key: env::var("CIRCLE_API_KEY").unwrap_or_default(),
            chain_id: env::var("CHAIN_ID")
                .unwrap_or_else(|_| "84532".into())
                .parse()?,
            usdc_address: env::var("USDC_ADDRESS")
                .unwrap_or_else(|_| "0x036CbD53842c5426634e7929541eC2318f3dCF7e".into()),
            circle_gateway: env::var("CIRCLE_GATEWAY")
                .unwrap_or_else(|_| "0x0000000000000000000000000000000000000000".into()),
            circle_api_url: env::var("CIRCLE_API_URL")
                .unwrap_or_else(|_| "https://api.circle.com".into()),
            server_port: env::var("SERVER_PORT")
                .unwrap_or_else(|_| "3000".into())
                .parse()?,
            payment_amount: env::var("PAYMENT_AMOUNT")
                .unwrap_or_else(|_| "1".into())
                .parse()?,
        })
    }
}
