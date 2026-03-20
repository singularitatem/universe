mod circle;
mod client;
mod config;
mod eip3009;
mod server;
mod wallet;

use std::sync::Arc;

use anyhow::Result;
use clap::{Parser, Subcommand};
use tokio::net::TcpListener;
use tracing::info;
use tracing_subscriber::{fmt, prelude::*, EnvFilter};

use client::PaymentClient;
use config::Config;
use wallet::Wallet;

#[derive(Parser)]
#[command(name = "nanopay", about = "USDC nanopayment service (x402 + Circle)")]
struct Cli {
    #[command(subcommand)]
    command: Commands,
}

#[derive(Subcommand)]
enum Commands {
    /// Start the x402 payee server
    Server,
    /// Pay for a resource at <URL> using x402
    Pay {
        /// Target URL (e.g. http://localhost:3000/api/data)
        url: String,
    },
    /// Check the status of a Circle payment
    Check {
        /// Payment ID returned by Circle
        payment_id: String,
    },
}

#[tokio::main]
async fn main() -> Result<()> {
    tracing_subscriber::registry()
        .with(fmt::layer())
        .with(EnvFilter::from_default_env())
        .init();

    let cli = Cli::parse();
    let config = Config::from_env()?;

    match cli.command {
        Commands::Server => {
            let port = config.server_port;
            let router = server::build_router(Arc::new(config));
            let listener = TcpListener::bind(format!("0.0.0.0:{port}")).await?;
            info!("nanopay server listening on :{port}");
            axum::serve(listener, router).await?;
        }

        Commands::Pay { url } => {
            let wallet = Wallet::from_config(&config)?;
            info!("Wallet address: {:#x}", wallet.address);
            let pay_client = PaymentClient::new(wallet, config);
            let result = pay_client.get_with_payment(&url).await?;
            println!("{}", serde_json::to_string_pretty(&result)?);
        }

        Commands::Check { payment_id } => {
            let circle = circle::CircleClient::new(&config);
            let payment = circle.get_payment(&payment_id).await?;
            println!("Payment ID:   {}", payment.id);
            println!("Status:       {}", payment.status);
            if let Some(tx) = payment.transaction_hash {
                println!("Tx Hash:      {tx}");
            }
        }
    }

    Ok(())
}
