use std::sync::Arc;

use axum::{
    body::Body,
    extract::State,
    http::{Request, StatusCode},
    middleware::{self, Next},
    response::{IntoResponse, Response},
    routing::get,
    Json, Router,
};
use serde_json::json;
use tracing::info;

use crate::{circle::CircleClient, config::Config, eip3009::TransferAuth};

#[derive(Clone)]
pub struct AppState {
    pub config: Arc<Config>,
    pub circle: Arc<CircleClient>,
}

/// x402 payment middleware: checks X-Payment header, validates & submits to Circle.
async fn payment_middleware(
    State(state): State<AppState>,
    req: Request<Body>,
    next: Next,
) -> Response {
    let headers = req.headers();

    if let Some(payment_header) = headers.get("x-payment") {
        // Parse the payment header as JSON TransferAuth
        match payment_header.to_str() {
            Ok(s) => match serde_json::from_str::<TransferAuth>(s) {
                Ok(auth) => {
                    let chain = format!("base-sepolia-{}", state.config.chain_id);
                    match state.circle.create_payment(&chain, auth).await {
                        Ok(payment) => {
                            info!("Payment accepted: {}", payment.id);
                            let mut resp = next.run(req).await;
                            resp.headers_mut().insert(
                                "x-payment-id",
                                payment.id.parse().unwrap(),
                            );
                            return resp;
                        }
                        Err(e) => {
                            return (
                                StatusCode::PAYMENT_REQUIRED,
                                Json(json!({ "error": format!("Payment failed: {e}") })),
                            )
                                .into_response();
                        }
                    }
                }
                Err(e) => {
                    return (
                        StatusCode::BAD_REQUEST,
                        Json(json!({ "error": format!("Invalid X-Payment JSON: {e}") })),
                    )
                        .into_response();
                }
            },
            Err(_) => {
                return (StatusCode::BAD_REQUEST, "Invalid header encoding").into_response();
            }
        }
    }

    // No payment header — return 402 with payment requirements
    let payment_required = json!({
        "x402Version": 1,
        "accepts": [{
            "scheme": "eip3009",
            "network": "base-sepolia",
            "chainId": state.config.chain_id,
            "usdcAddress": state.config.usdc_address,
            "payTo": state.config.circle_gateway,
            "maxAmountRequired": state.config.payment_amount.to_string(),
            "description": "Access to /api/data requires a micropayment"
        }]
    });

    (
        StatusCode::PAYMENT_REQUIRED,
        [("x-payment-required", payment_required.to_string())],
        Json(payment_required),
    )
        .into_response()
}

async fn data_handler() -> Json<serde_json::Value> {
    Json(json!({
        "message": "Hello from the paid API!",
        "data": [1, 2, 3, 4, 5]
    }))
}

async fn health_handler() -> Json<serde_json::Value> {
    Json(json!({ "status": "ok" }))
}

pub fn build_router(config: Arc<Config>) -> Router {
    let state = AppState {
        circle: Arc::new(CircleClient::new(&config)),
        config,
    };

    Router::new()
        .route(
            "/api/data",
            get(data_handler).layer(middleware::from_fn_with_state(
                state.clone(),
                payment_middleware,
            )),
        )
        .route("/health", get(health_handler))
        .with_state(state)
}
