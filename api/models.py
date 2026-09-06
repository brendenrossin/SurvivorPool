from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, ForeignKey, Float, Index
from sqlalchemy import text as sql_text   # `text` is also a column name below
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from api.database import Base

class Player(Base):
    __tablename__ = "players"

    player_id = Column(Integer, primary_key=True)
    display_name = Column(String, unique=True, nullable=False)

    picks = relationship("Pick", back_populates="player")

class Pick(Base):
    __tablename__ = "picks"

    pick_id = Column(Integer, primary_key=True)
    player_id = Column(Integer, ForeignKey("players.player_id"))
    season = Column(Integer, nullable=False)
    week = Column(Integer, nullable=False)
    team_abbr = Column(String)
    source = Column(String, nullable=False, default="google_sheets")
    picked_at = Column(DateTime(timezone=True), server_default=func.now())

    player = relationship("Player", back_populates="picks")
    result = relationship("PickResult", back_populates="pick", uselist=False)

    __table_args__ = (
        # The no-reusing-a-team rule, enforced by the database rather than by
        # ingestion remembering to check. Partial because a blank cell in the
        # sheet is a real state - a player who has not picked yet - and several
        # of those per player must not collide.
        Index("uniq_player_team_season", "player_id", "season", "team_abbr",
              unique=True,
              postgresql_where=sql_text("team_abbr IS NOT NULL"),
              sqlite_where=sql_text("team_abbr IS NOT NULL")),
        Index("idx_picks_season_week", "season", "week"),
    )

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

    __table_args__ = (
        Index("idx_games_season_week", "season", "week"),
        Index("idx_games_status", "status"),
        Index("idx_games_point_spread", "point_spread"),
        Index("idx_games_favorite_team", "favorite_team"),
    )

class PickResult(Base):
    __tablename__ = "pick_results"

    pick_id = Column(Integer, ForeignKey("picks.pick_id", ondelete="CASCADE"), primary_key=True)
    game_id = Column(String, ForeignKey("games.game_id"))
    is_valid = Column(Boolean, nullable=False, default=True)
    is_locked = Column(Boolean, nullable=False, default=False)
    survived = Column(Boolean)

    pick = relationship("Pick", back_populates="result")
    game = relationship("Game", back_populates="pick_results")

    __table_args__ = (
        Index("idx_pick_results_survived", "survived"),
    )

class JobMeta(Base):
    __tablename__ = "job_meta"

    job_name = Column(String, primary_key=True)
    last_success_at = Column(DateTime(timezone=True))
    last_run_at = Column(DateTime(timezone=True))
    status = Column(String)
    message = Column(Text)

class ChatMessage(Base):
    __tablename__ = "chat_messages"

    message_id = Column(String, primary_key=True)   # GroupMe's own id
    group_id = Column(String, nullable=False)
    sender_id = Column(String)
    sender_name = Column(String)
    sender_type = Column(String)                    # "user" | "bot" | "system"
    text = Column(String)
    favorite_count = Column(Integer, nullable=False, default=0)
    is_system = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), nullable=False)

    # The corpus read is a single shape: the most-liked human messages before a
    # cutoff. Two independent single-column indexes could serve either the
    # filter or the sort but never both from one scan, and `sender_type != 'bot'`
    # is an inequality a plain btree cannot seek on at all. Baking the fixed
    # predicates into a partial index leaves exactly that query's rows, already
    # in its sort order. Must stay identical to idx_chat_messages_corpus in
    # db/migrations.sql - tests build the schema from here on SQLite, production
    # builds it from the .sql on Postgres.
    __table_args__ = (
        Index("idx_chat_messages_corpus",
              favorite_count.desc(), "created_at",
              postgresql_where=sql_text("is_system = false AND sender_type != 'bot'")),
    )
