use alloy::{
    primitives::{Address, B256, U256},
    signers::local::PrivateKeySigner,
};
use anyhow::{Context, Result};
use std::time::{SystemTime, UNIX_EPOCH};
use uuid::Uuid;

use crate::{config::Config, eip3009::{sign_transfer_authorization, TransferAuth}};

pub struct Wallet {
    pub signer: PrivateKeySigner,
    pub address: Address,
}

impl Wallet {
    pub fn from_config(config: &Config) -> Result<Self> {
        let key = config.private_key.trim_start_matches("0x");
        let signer: PrivateKeySigner = key.parse().context("invalid private key")?;
        let address = signer.address();
        Ok(Self { signer, address })
    }

    pub async fn sign_transfer(
        &self,
        to: Address,
        value: U256,
        config: &Config,
    ) -> Result<TransferAuth> {
        let now = SystemTime::now()
            .duration_since(UNIX_EPOCH)?
            .as_secs();

        let valid_after = U256::ZERO;
        let valid_before = U256::from(now + 3600); // 1 hour

        // Use a UUID v4 as the nonce (32 bytes)
        let uuid = Uuid::new_v4();
        let uuid_bytes = uuid.as_bytes();
        let mut nonce_bytes = [0u8; 32];
        nonce_bytes[..16].copy_from_slice(uuid_bytes);
        let nonce = B256::from(nonce_bytes);

        let usdc: Address = config.usdc_address.parse().context("invalid USDC address")?;

        sign_transfer_authorization(
            &self.signer,
            self.address,
            to,
            value,
            valid_after,
            valid_before,
            nonce,
            config.chain_id,
            usdc,
        )
        .await
    }
}
