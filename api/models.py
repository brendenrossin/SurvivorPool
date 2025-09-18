from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from api.database import Base

class Player(Base):
    __tablename__ = "players"

    player_id = Column(Integer, primary_key=True, index=True)
    display_name = Column(String, unique=True, nullable=False)

    picks = relationship("Pick", back_populates="player")

class Pick(Base):
    __tablename__ = "picks"

    pick_id = Column(Integer, primary_key=True, index=True)
    player_id = Column(Integer, ForeignKey("players.player_id"))
    season = Column(Integer, nullable=False)
    week = Column(Integer, nullable=False)
    team_abbr = Column(String)
    source = Column(String, nullable=False, default="google_sheets")
    picked_at = Column(DateTime(timezone=True), server_default=func.now())

    player = relationship("Player", back_populates="picks")
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