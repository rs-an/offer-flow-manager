from alembic import op
import sqlalchemy as sa

revision = "001"
down_revision = None

def upgrade():
    op.create_table("campaigns", sa.Column("id", sa.Integer, primary_key=True), sa.Column("name", sa.String, nullable=False))
    op.create_table("streams", sa.Column("id", sa.Integer, primary_key=True), sa.Column("campaign_id", sa.Integer, sa.ForeignKey("campaigns.id"), nullable=False), sa.Column("name", sa.String, nullable=False), sa.Column("published", sa.JSON, nullable=False), sa.Column("draft", sa.JSON, nullable=False))

def downgrade():
    op.drop_table("streams")
    op.drop_table("campaigns")
