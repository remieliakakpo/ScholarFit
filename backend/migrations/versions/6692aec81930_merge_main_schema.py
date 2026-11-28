"""reprise de la fusion parallèle de main (étape vide)

Une autre fusion de main dans cette branche avait créé cette migration juste après 0006, avec
les mêmes tables que la 0007 (paiements, journal des e-mails, documents d'accompagnement). Pour une
seule chaîne de migrations, la 0007 fait tout le travail et celle-ci est vide. Son numéro est gardé :
une base déjà passée par l'ancienne version reste reconnue comme à jour.

Revision ID: 6692aec81930
Revises: 0007
Create Date: 2026-11-28 11:40:24.236810
"""

revision = '6692aec81930'
down_revision = '0007'
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
