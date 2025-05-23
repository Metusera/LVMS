"""Added disability column to Visitor

Revision ID: 4d712afa0055
Revises: 
Create Date: 2025-05-12 11:15:34.055618

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '4d712afa0055'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('visitor', schema=None) as batch_op:
        batch_op.add_column(sa.Column('disability', sa.String(length=50), nullable=True))

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('visitor', schema=None) as batch_op:
        batch_op.drop_column('disability')

    # ### end Alembic commands ###
