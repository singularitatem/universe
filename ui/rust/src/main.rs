use axum::{extract::Query, response::Html, routing::get, Router};
use serde::Deserialize;

const INDEX_HTML: &str = include_str!("../../static/index.html");

#[derive(Deserialize)]
struct AskParams {
    q: Option<String>,
}

async fn index() -> Html<&'static str> {
    Html(INDEX_HTML)
}

async fn ask(Query(params): Query<AskParams>) -> String {
    let message = params.q.unwrap_or_default();
    format!(
        "You asked: \"{message}\"\n\n\
         This is a fixed response from the server. \
         The backend received your message successfully!"
    )
}

#[tokio::main]
async fn main() {
    let app = Router::new()
        .route("/", get(index))
        .route("/ask", get(ask));

    let listener = tokio::net::TcpListener::bind("127.0.0.1:8080")
        .await
        .unwrap();

    println!("Listening on http://127.0.0.1:8080");
    axum::serve(listener, app).await.unwrap();
}
