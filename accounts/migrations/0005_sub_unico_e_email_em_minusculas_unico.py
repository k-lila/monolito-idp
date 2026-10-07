import uuid

import django.db.models.functions.text
import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):
    """Só esquema: as restrições sobre os valores que a 0002 e a 0004 deixaram."""

    dependencies = [
        ("accounts", "0004_sub_e_updated_at_das_contas_atuais"),
    ]

    operations = [
        migrations.AlterField(
            model_name="user",
            name="sub",
            field=models.UUIDField(default=uuid.uuid4, editable=False, unique=True),
        ),
        migrations.AlterField(
            model_name="user",
            name="updated_at",
            field=models.DateTimeField(default=django.utils.timezone.now),
        ),
        migrations.AddConstraint(
            model_name="user",
            constraint=models.UniqueConstraint(
                django.db.models.functions.text.Lower("email"),
                name="accounts_user_email_minusculas_unico",
                violation_error_message="Já existe uma conta com este e-mail.",
            ),
        ),
    ]
