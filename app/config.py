from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    plex_url: str = Field(default="http://plex:32400", alias="PLEX_URL")
    plex_token: str = Field(default="")
    default_music_section: str = Field(default="Music", alias="DEFAULT_MUSIC_SECTION")
    default_replace_playlist: bool = Field(default=True, alias="DEFAULT_REPLACE_PLAYLIST")
    app_port: int = Field(default=8080, alias="APP_PORT")
    match_confidence_threshold: float = Field(default=70.0, alias="MATCH_CONFIDENCE_THRESHOLD")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )


settings = Settings()
