import uuid

from django.db import migrations
from django.db.models import F


def preencher(apps, schema_editor):
    User = apps.get_model("accounts", "User")
    # Um UUID por conta, em laço: um update() só daria o mesmo valor a todas.
    for user in User.objects.only("id"):
        User.objects.filter(pk=user.pk).update(sub=uuid.uuid4())
    User.objects.update(updated_at=F("date_joined"))


class Migration(migrations.Migration):
    """Só dados. `email_verified` já nasceu falso pelo AddField da 0003."""

    dependencies = [
        ("accounts", "0003_campos_da_conta"),
    ]

    operations = [
        # Irreversível: desfazer e refazer sortearia outro UUID por conta, e as linhas da trilha
        # gravadas com o primeiro ficariam órfãs.
        migrations.RunPython(preencher),
    ]
