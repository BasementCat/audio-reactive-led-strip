"""Updates

Revision ID: 05ae88c17916
Revises: b41a0816fcda
Create Date: 2020-04-14 07:42:55.734257

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '05ae88c17916'
down_revision = 'b41a0816fcda'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('effect_group', sa.Column('color', sa.Unicode(length=16), server_default='PINK:4', nullable=False))
    op.add_column('effect_to_effect_group', sa.Column('lights', sa.UnicodeText(), server_default='*', nullable=False))
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('effect_to_effect_group', 'lights')
    op.drop_column('effect_group', 'color')
    # ### end Alembic commands ###
