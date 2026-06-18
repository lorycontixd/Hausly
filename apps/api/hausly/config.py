from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Database
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/hausly"

    # Firebase
    firebase_project_id: str = "hausly-dev"
    firebase_service_account_path: str = "./firebase-sa.json"

    # Azure SignalR
    signalr_connection_string: str = ""

    # Azure OpenAI (v3+)
    ai_provider: str = "azure_openai"
    azure_openai_endpoint: str = ""
    azure_openai_key: str = ""

    # Azure Application Insights
    appinsights_connection_string: str = ""
    
    # CORS
    cors_origins: str = "http://localhost:8081,http://localhost:19006"

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",")]

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
