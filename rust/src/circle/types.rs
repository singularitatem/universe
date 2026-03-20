use serde::{Deserialize, Serialize};

use crate::eip3009::TransferAuth;

#[derive(Debug, Serialize)]
pub struct CreatePaymentRequest {
    pub chain: String,
    pub authorization: TransferAuth,
}

#[derive(Debug, Deserialize)]
pub struct CreatePaymentResponse {
    pub data: PaymentData,
}

#[derive(Debug, Deserialize)]
pub struct GetPaymentResponse {
    pub data: PaymentData,
}

#[derive(Debug, Deserialize, Clone)]
pub struct PaymentData {
    pub id: String,
    pub status: String,
    #[serde(rename = "transactionHash")]
    pub transaction_hash: Option<String>,
}

#[derive(Debug, Deserialize)]
pub struct CircleErrorResponse {
    pub code: Option<i32>,
    pub message: Option<String>,
}
