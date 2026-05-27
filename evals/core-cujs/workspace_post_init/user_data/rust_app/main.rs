use actix_web::{get, post, web, App, HttpServer, HttpResponse, Responder, middleware::Logger};
use serde::{Deserialize, Serialize};
use serde_json::{json, Value};

// ==========================================
// DATA MODELS (Domain Entities)
// ==========================================

#[derive(Serialize, Deserialize, Clone)]
pub struct User {
    pub user_id: i32,
    pub username: String,
    pub first_name: Option<String>,
    pub last_name: Option<String>,
    pub role_id: Option<i32>,
    pub active: Option<String>,
}

#[derive(Serialize, Deserialize, Clone)]
pub struct Post {
    pub post_id: i32,
    pub user_id: i32,
    pub title: String,
    pub content: String,
    pub published_at: Option<String>,
    pub views_count: i32,
    pub metadata: Option<Value>, // Uses JSONB in Postgres
}

#[derive(Serialize, Deserialize, Clone)]
pub struct Comment {
    pub comment_id: i32,
    pub post_id: i32,
    pub user_id: i32,
    pub content: String,
}

#[derive(Serialize, Deserialize, Clone)]
pub struct MediaUpload {
    pub post_id: Option<i32>,
    pub filename: String,
    pub file_type: String,
    pub access_rights: Option<Value>, 
}

// ==========================================
// API HANDLERS (Stubs)
// ==========================================

// --- IAM Module ---

#[get("/api/v1/users/{user_id}")]
async fn get_user(path: web::Path<i32>) -> impl Responder {
    let user_id = path.into_inner();
    // STUB: Fetch from database
    let user = User {
        user_id,
        username: format!("user_{}", user_id),
        first_name: Some("Jane".to_string()),
        last_name: Some("Doe".to_string()),
        role_id: Some(1),
        active: Some("Y".to_string()),
    };
    HttpResponse::Ok().json(user)
}

#[post("/api/v1/users")]
async fn create_user(user_req: web::Json<User>) -> impl Responder {
    // STUB: Insert into database
    HttpResponse::Created().json(json!({
        "status": "success", 
        "message": "User created", 
        "data": user_req.into_inner()
    }))
}

// --- Content Module ---

#[get("/api/v1/posts")]
async fn list_posts() -> impl Responder {
    // STUB: Query database for posts
    let posts = vec![
        Post {
            post_id: 101,
            user_id: 1,
            title: "Platform Launch Architecture".to_string(),
            content: "Exploring the new microservices backend...".to_string(),
            published_at: Some("2026-05-27T10:00:00Z".to_string()),
            views_count: 245,
            metadata: Some(json!({"tags": ["rust", "backend", "actix"]})),
        }
    ];
    HttpResponse::Ok().json(posts)
}

#[post("/api/v1/posts")]
async fn create_post(post_req: web::Json<Post>) -> impl Responder {
    // STUB: Insert post into database
    HttpResponse::Created().json(json!({
        "status": "success",
        "message": "Post published",
        "post_id": 102
    }))
}

#[post("/api/v1/posts/{post_id}/comments")]
async fn add_comment(path: web::Path<i32>, comment_req: web::Json<Comment>) -> impl Responder {
    let post_id = path.into_inner();
    // STUB: Verify post exists, insert comment into database
    HttpResponse::Created().json(json!({
        "status": "success",
        "message": format!("Comment added to post {}", post_id),
        "comment_id": 505
    }))
}

// --- Media Module ---

#[post("/api/v1/media")]
async fn upload_media(media_req: web::Json<MediaUpload>) -> impl Responder {
    // STUB: Handle file upload stream, encrypt if necessary, save metadata to DB
    HttpResponse::Accepted().json(json!({
        "status": "processing",
        "message": "Media upload received and is being processed",
        "file_path": format!("/storage/encrypted/{}", media_req.filename)
    }))
}

// ==========================================
// SERVER BOOTSTRAP
// ==========================================

#[actix_web::main]
async fn main() -> std::io::Result<()> {
    // Initialize standard logger
    env_logger::init_from_env(env_logger::Env::new().default_filter_or("info"));

    println!("Starting Cloudaicompanion API server at http://127.0.0.1:8080");

    HttpServer::new(|| {
        App::new()
            .wrap(Logger::default())
            // Register route handlers
            .service(get_user)
            .service(create_user)
            .service(list_posts)
            .service(create_post)
            .service(add_comment)
            .service(upload_media)
    })
    .bind(("127.0.0.1", 8080))?
    .run()
    .await
}
