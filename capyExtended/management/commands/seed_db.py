# capyExtended/management/commands/seed_db.py

from django.core.management.base import BaseCommand
from django.db import transaction  # Para garantir atomicidade
from capyExtended.models import CustomUser, Item  # Importa seus modelos


class Command(BaseCommand):
    """
    Popula o banco de dados com dados iniciais de exemplo (Usuários e Itens).
    """
    help = 'Popula o banco de dados com dados iniciais (Usuários e Itens)'

    def _create_or_get_user(self, email, defaults, password):
        """Cria ou obtém um usuário, definindo a senha se criado."""
        user, created = CustomUser.objects.get_or_create(
            email=email, defaults=defaults
        )
        if created:
            user.set_password(password)
            user.save()
            self.stdout.write(self.style.SUCCESS(
                f'Usuário "{user.email}" criado.'
            ))
        else:
            self.stdout.write(f'Usuário "{user.email}" já existia.')
        return user

    def _create_or_get_item(self, title, defaults):
        """Cria ou obtém um item."""
        item, created = Item.objects.get_or_create(
            title=title, defaults=defaults
        )
        if created:
            self.stdout.write(self.style.SUCCESS(
                f'Item "{item.title}" criado.'
            ))
        else:
            self.stdout.write(f'Item "{item.title}" já existia.')
        return item

    @transaction.atomic  # Garante que ou tudo é criado, ou nada é
    def handle(self, *args, **options):
        """Executa o processo de seeding."""
        self.stdout.write(self.style.WARNING(
            'Iniciando o processo de seed...'
        ))

        # --- Check/Create Users ---
        self.stdout.write('Creating/Checking Users...')

        user1_defaults = {
            'username': 'seeduser1',
            'first_name': 'Seed',
            'last_name': 'User One',
            'is_staff': False,
            'is_superuser': False,
            'email_confirmed': True,  # Confirmar para testar restrição
        }
        user1 = self._create_or_get_user(
            'seeduser1@example.com', user1_defaults, 'SeedPass1!'
        )

        user2_defaults = {
            'username': 'seeduser2',
            'first_name': 'Seed',
            'last_name': 'User Two',
            'email_confirmed': False,  # Deixar este não confirmado
        }
        user2 = self._create_or_get_user(
            'seeduser2@example.com', user2_defaults, 'SeedPass2@'
        )

        # --- Check/Create Items ---
        self.stdout.write('Creating/Checking Items...')

        self._create_or_get_item(
            title='Item Público Seed 1 (User 1)',
            defaults={
                'owner': user1,
                'description': 'Descrição do item público 1.',
                'is_public': True
            }
        )
        self._create_or_get_item(
            title='Item Restrito Seed 1 (User 1)',
            defaults={
                'owner': user1,
                'description': 'Descrição do item restrito 1.',
                'is_public': False
            }
        )
        self._create_or_get_item(
            title='Item Público Seed 2 (User 2)',
            defaults={
                'owner': user2,
                'description': 'Descrição do item público 2.',
                'is_public': True
            }
        )
        self._create_or_get_item(
            title='Item Restrito Seed 2 (User 2)',
            defaults={
                'owner': user2,
                'description': 'Descrição do item restrito 2.',
                'is_public': False
            }
        )

        self.stdout.write(self.style.SUCCESS('Processo de Seed concluído!'))
