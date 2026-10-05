"""initial schema

Revision ID: ec6c811c8c40
Revises:
Create Date: 2026-09-05 20:48:01.140308

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ec6c811c8c40'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('airports',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=50), nullable=False),
    sa.Column('city', sa.String(length=50), nullable=False),
    sa.Column('country', sa.String(length=50), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_airports_name'), 'airports', ['name'], unique=False)
    op.create_index(op.f('ix_airports_city'), 'airports', ['city'], unique=False)
    op.create_index(op.f('ix_airports_country'), 'airports', ['country'], unique=False)

    op.create_table('users',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=50), nullable=False),
    sa.Column('is_admin', sa.Boolean(), server_default=sa.text('0'), nullable=False),
    sa.Column('email', sa.String(length=255), nullable=False),
    sa.Column('hashed_password', sa.String(length=255), nullable=False),
    sa.Column('phone_number', sa.String(length=50), nullable=True),
    sa.Column('city', sa.String(length=50), nullable=False),
    sa.Column('country', sa.String(length=50), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_users_email'), 'users', ['email'], unique=True)

    op.create_table('flights',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('airline_name', sa.String(length=50), nullable=False),
    sa.Column('departure_airport', sa.Integer(), nullable=False),
    sa.Column('arrival_airport', sa.Integer(), nullable=False),
    sa.Column('start_time', sa.DateTime(), nullable=False),
    sa.Column('end_time', sa.DateTime(), nullable=False),
    sa.Column('price', sa.Numeric(precision=10, scale=2), nullable=False),
    sa.Column('total_seats', sa.Integer(), nullable=False),
    sa.Column('available_seats', sa.Integer(), nullable=False),
    sa.Column('flight_class', sa.Enum('ECONOMY', 'BUSINESS', 'FIRST', name='flightclass', native_enum=False, length=20), nullable=False),
    sa.ForeignKeyConstraint(['arrival_airport'], ['airports.id'], ),
    sa.ForeignKeyConstraint(['departure_airport'], ['airports.id'], ),
    sa.PrimaryKeyConstraint('id'),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('flights')
    op.drop_index(op.f('ix_users_email'), table_name='users')
    op.drop_table('users')
    op.drop_index(op.f('ix_airports_country'), table_name='airports')
    op.drop_index(op.f('ix_airports_city'), table_name='airports')
    op.drop_index(op.f('ix_airports_name'), table_name='airports')
    op.drop_table('airports')
