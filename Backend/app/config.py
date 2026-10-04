from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    
    openai_api_key: str = ""
    chat_model: str = "gpt-4o-mini"
    embedding_model: str = "text-embedding-3-small"
    embedding_dim: int = 1536
    
    aws_region: str = "us-east-1"
    aws_access_key_id: str | None = None
    aws_secret_access_key: str | None = None
    dynamodb_table: str = "alibi-sessions"
    dynamodb_endpoint_url: str | None = None  # http://localhost:8001 for DynamoDB Local
    auto_create_table: bool = True
    
    pinecone_api_key: str = ""
    pinecone_index: str = "alibi-cold-storage"
    pinecone_cloud: str = "aws"
    pinecone_region: str = "us-east-1"
    
    default_strategy: str = "fit_to_budget"
    default_budget_tokens: int = 800
    default_last_n: int = 8
    recall_budget_tokens: int = 300
    recall_top_k: int = 4

    # Game
    max_player_turns: int = 25

    cors_origins: list[str] = ["http://localhost:5173"]
    
@lru_cache
def get_settings() -> Settings:
    return Settings()
