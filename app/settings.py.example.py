from pydantic import BaseSettings, Field, validator


class Settings(BaseSettings):
    env: str = Field("prod", env="ENV")
    app_url: str = Field("http://127.0.0.1:8080", env="APP_URL")
    db_uri: str = Field(
        "postgresql://trialstreamer:[PASSWORD]@localhost:5432/trialstreamer", env="DB_URI"
    )
    github_client_id: str = Field("[ADD GITHUB CLIENT ID HERE]", env="GITHUB_CLIENT_ID")
    github_client_secret: str = Field("[ADD GITHUB CLIENT SECRET HERE]", env="GITHUB_CLIENT_SECRET")
    jwt_secret_key: str = Field("example_key_super_secret", env="JWT_SECRET_KEY")
    jwt_algorithm: str = Field("HS256", env="JWT_ALGORITHM")
    github_whitelist: list = ["[github_id_1]", "[github_id_2]"]

    class Config:
        env_file = '.env'


settings = Settings()
