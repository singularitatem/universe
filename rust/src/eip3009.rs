use alloy::{
    primitives::{Address, B256, U256},
    signers::Signer,
    sol,
    sol_types::{eip712_domain, SolStruct},
};
use anyhow::Result;
use serde::{Deserialize, Serialize};

sol! {
    struct TransferWithAuthorization {
        address from;
        address to;
        uint256 value;
        uint256 validAfter;
        uint256 validBefore;
        bytes32 nonce;
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TransferAuth {
    pub from: String,
    pub to: String,
    pub value: String,
    pub valid_after: String,
    pub valid_before: String,
    pub nonce: String,
    pub v: u8,
    pub r: String,
    pub s: String,
}

pub async fn sign_transfer_authorization(
    signer: &impl Signer,
    from: Address,
    to: Address,
    value: U256,
    valid_after: U256,
    valid_before: U256,
    nonce: B256,
    chain_id: u64,
    usdc_address: Address,
) -> Result<TransferAuth> {
    let domain = eip712_domain! {
        name: "USD Coin",
        version: "2",
        chain_id: chain_id,
        verifying_contract: usdc_address,
    };

    let transfer = TransferWithAuthorization {
        from,
        to,
        value,
        validAfter: valid_after,
        validBefore: valid_before,
        nonce,
    };

    let hash = transfer.eip712_signing_hash(&domain);
    let sig = signer.sign_hash(&hash).await?;

    Ok(TransferAuth {
        from: format!("{from:#x}"),
        to: format!("{to:#x}"),
        value: value.to_string(),
        valid_after: valid_after.to_string(),
        valid_before: valid_before.to_string(),
        nonce: format!("{nonce:#x}"),
        v: sig.v() as u8 + 27,
        r: format!("{:#x}", sig.r()),
        s: format!("{:#x}", sig.s()),
    })
}
