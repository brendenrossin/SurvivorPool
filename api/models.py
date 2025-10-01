from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, ForeignKey, Float, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from api.database import Base

class League(Base):
    """
    League model - represents a survivor pool league
    Each league can have its own players, picks, and settings
    """
    __tablename__ = "leagues"

    league_id = Column(Integer, primary_key=True, index=True)
    league_name = Column(String, nullable=False)
    league_slug = Column(String, unique=True, nullable=False, index=True)
    pick_source = Column(String, nullable=False, default="google_sheets")  # 'google_sheets' or 'in_app'
    google_sheet_id = Column(String)  # NULL if pick_source='in_app'
    season = Column(Integer, nullable=False)
    commissioner_email = Column(String)
    invite_code = Column(String, unique=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    settings = Column(JSON, default={})

    # Relationships
    players = relationship("Player", back_populates="league")
    picks = relationship("Pick", back_populates="league")
    commissioners = relationship("LeagueCommissioner", back_populates="league")

class Player(Base):
    __tablename__ = "players"

    player_id = Column(Integer, primary_key=True, index=True)
    display_name = Column(String, nullable=False)  # Removed unique constraint (can have same name in different leagues)
    league_id = Column(Integer, ForeignKey("leagues.league_id", ondelete="CASCADE"), nullable=False, index=True)

    # Relationships
    picks = relationship("Pick", back_populates="player")
    league = relationship("League", back_populates="players")
    user_players = relationship("UserPlayer", back_populates="player")

class Pick(Base):
    __tablename__ = "picks"

    pick_id = Column(Integer, primary_key=True, index=True)
    player_id = Column(Integer, ForeignKey("players.player_id"))
    league_id = Column(Integer, ForeignKey("leagues.league_id", ondelete="CASCADE"), nullable=False, index=True)
    season = Column(Integer, nullable=False)
    week = Column(Integer, nullable=False)
    team_abbr = Column(String)
    source = Column(String, nullable=False, default="google_sheets")
    picked_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    player = relationship("Player", back_populates="picks")
    league = relationship("League", back_populates="picks")
    result = relationship("PickResult", back_populates="pick", uselist=False)

class Game(Base):
    __tablename__ = "games"

    game_id = Column(String, primary_key=True)
    season = Column(Integer, nullable=False)
    week = Column(Integer, nullable=False)
    kickoff = Column(DateTime(timezone=True), nullable=False)
    home_team = Column(String, nullable=False)
    away_team = Column(String, nullable=False)
    status = Column(String, nullable=False)
    home_score = Column(Integer)
    away_score = Column(Integer)
    winner_abbr = Column(String)
    # Betting odds fields
    point_spread = Column(Float)  # Positive = home team favored by this many points
    favorite_team = Column(String)  # Which team is favored according to spread

    pick_results = relationship("PickResult", back_populates="game")

class PickResult(Base):
    __tablename__ = "pick_results"

    pick_id = Column(Integer, ForeignKey("picks.pick_id", ondelete="CASCADE"), primary_key=True)
    game_id = Column(String, ForeignKey("games.game_id"))
    is_valid = Column(Boolean, nullable=False, default=True)
    is_locked = Column(Boolean, nullable=False, default=False)
    survived = Column(Boolean)

    pick = relationship("Pick", back_populates="result")
    game = relationship("Game", back_populates="pick_results")

class JobMeta(Base):
    __tablename__ = "job_meta"

    job_name = Column(String, primary_key=True)
    last_success_at = Column(DateTime(timezone=True))
    last_run_at = Column(DateTime(timezone=True))
    status = Column(String)
    message = Column(Text)

# ============================================================================
# MULTI-LEAGUE SUPPORT - New Models for User Management
# ============================================================================

class User(Base):
    """
    User model - represents an authenticated user who can manage players across leagues
    """
    __tablename__ = "users"

    user_id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, nullable=False, index=True)
    password_hash = Column(String)  # NULL if using magic links/OAuth
    auth_provider = Column(String, default="email")  # 'email', 'google', 'magic_link'
    is_verified = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    last_login_at = Column(DateTime(timezone=True))

    # Relationships
    user_players = relationship("UserPlayer", back_populates="user")
    league_commissions = relationship("LeagueCommissioner", back_populates="user")

class UserPlayer(Base):
    """
    Junction table linking users to their players in various leagues
    One user can have players in multiple leagues
    """
    __tablename__ = "user_players"

    user_id = Column(Integer, ForeignKey("users.user_id", ondelete="CASCADE"), primary_key=True)
    player_id = Column(Integer, ForeignKey("players.player_id", ondelete="CASCADE"), primary_key=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    user = relationship("User", back_populates="user_players")
    player = relationship("Player", back_populates="user_players")

class LeagueCommissioner(Base):
    """
    Tracks who can manage each league (commissioners and admins)
    """
    __tablename__ = "league_commissioners"

    league_id = Column(Integer, ForeignKey("leagues.league_id", ondelete="CASCADE"), primary_key=True)
    user_id = Column(Integer, ForeignKey("users.user_id", ondelete="CASCADE"), primary_key=True)
    role = Column(String, default="commissioner")  # 'commissioner' or 'admin'
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    league = relationship("League", back_populates="commissioners")
    user = relationship("User", back_populates="league_commissions")