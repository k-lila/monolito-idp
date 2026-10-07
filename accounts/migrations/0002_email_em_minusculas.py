from django.db import migrations
from django.db.models import Count
from django.db.models.functions import Lower


def email_em_minusculas(apps, schema_editor):
    User = apps.get_model("accounts", "User")
    em_colisao = (
        User.objects.annotate(minusculo=Lower("email"))
        .values("minusculo")
        .annotate(contas=Count("id"))
        .filter(contas__gt=1)
        .values("minusculo")
    )
    ids = list(
        User.objects.annotate(minusculo=Lower("email"))
        .filter(minusculo__in=em_colisao)
        .order_by("id")
        .values_list("id", flat=True)
    )
    # Para antes de qualquer escrita. A mensagem leva os `id`, nunca os e-mails: ela vai ao
    # log do entrypoint.
    if ids:
        raise RuntimeError(
            "Contas cujo e-mail só difere pela caixa, por id: "
            f"{', '.join(map(str, ids))}. Nenhuma conta foi alterada; resolva as colisões "
            "antes de migrar."
        )
    User.objects.update(email=Lower("email"))


class Migration(migrations.Migration):
    """Só dados. Vem antes do esquema: a colisão para a implantação sem estado parcial."""

    dependencies = [
        ("accounts", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(email_em_minusculas, migrations.RunPython.noop),
    ]
