# capy/tests.py

import uuid
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase, APIClient

from .models import CustomUser, Item


# --- Helper Function ---
def create_test_user(
    username: str, email: str, password: str, confirmed: bool = False
) -> CustomUser:
    """Cria um usuário de teste."""
    user = CustomUser.objects.create_user(
        username=username,
        email=email,
        password=password,
        first_name=username.capitalize(),
        last_name="Test",
        email_confirmed=confirmed
    )
    # Save again if manually confirmed to ensure state
    # (although create_user already saves)
    if confirmed:
        user.save()
    return user


class BaseAPITestCase(APITestCase):
    """ Classe base com métodos auxiliares para testes de API. """
    client: APIClient
    user: CustomUser

    def _get_jwt_tokens_for_user(self, email: str, password: str) -> dict:
        """Obtém os tokens JWT para um usuário."""
        token_url = reverse('token_obtain_pair')
        response = self.client.post(
            token_url, {'email': email, 'password': password}, format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('access', response.data)
        self.assertIn('refresh', response.data)
        return response.data

    def _authenticate_client(self, access_token: str) -> None:
        """Configura o cliente de teste com o token de autenticação JWT."""
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {access_token}')

    def _clear_authentication(self) -> None:
        """Limpa a autenticação do cliente de teste."""
        self.client.credentials()


# --- Registration and Login Tests ---
class UserRegistrationLoginTests(BaseAPITestCase):
    """ Testes para os endpoints de registro e obtenção de token. """

    def setUp(self) -> None:
        """ Define URLs e dados comuns para os testes desta classe. """
        self.register_url = reverse('capyExtended:register')
        self.token_url = reverse('token_obtain_pair')
        self.register_data = {
            "username": "testregistrar",
            "email": "testregistrar@example.com",
            "first_name": "Test",
            "last_name": "Registrar",
            "password": "StrongPassword123",
            "password2": "StrongPassword123",
        }
        # Existing user for duplication/login tests
        self.existing_user = create_test_user(
            'existinguser', 'existing@example.com', 'ExistingPassword123'
        )

    def test_registration_success(self) -> None:
        """ Testa o registro bem-sucedido de um novo usuário. """
        initial_count = CustomUser.objects.count()
        response = self.client.post(
            self.register_url, self.register_data, format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        # Check if the user count increased by 1
        self.assertEqual(CustomUser.objects.count(), initial_count + 1)
        # Check if the user was created with the correct data
        user_exists = CustomUser.objects.filter(
            email=self.register_data['email']
        ).exists()
        self.assertTrue(user_exists)
        user = CustomUser.objects.get(email=self.register_data['email'])
        self.assertFalse(user.email_confirmed)
        self.assertIn('id', response.data)
        self.assertEqual(response.data['email'], self.register_data['email'])
        self.assertNotIn('password', response.data)

    def test_registration_fail_duplicate_email(self) -> None:
        """ Testa a falha no registro com email duplicado. """
        initial_count = CustomUser.objects.count()
        dup_email_data = self.register_data.copy()
        dup_email_data['email'] = self.existing_user.email
        response = self.client.post(
            self.register_url, dup_email_data, format='json'
        )
        self.assertEqual(
            response.status_code, status.HTTP_400_BAD_REQUEST
        )
        self.assertIn('email', response.data)
        # No new user
        self.assertEqual(CustomUser.objects.count(), initial_count)

    def test_registration_fail_duplicate_username(self) -> None:
        """ Testa a falha no registro com username duplicado. """
        initial_count = CustomUser.objects.count()
        dup_username_data = self.register_data.copy()
        # Existing username
        dup_username_data['username'] = self.existing_user.username
        response = self.client.post(
            self.register_url, dup_username_data, format='json'
        )
        self.assertEqual(
            response.status_code, status.HTTP_400_BAD_REQUEST
        )
        self.assertIn('username', response.data)
        self.assertEqual(CustomUser.objects.count(), initial_count)

    def test_registration_fail_password_mismatch(self) -> None:
        """ Testa a falha no registro com senhas não coincidentes. """
        initial_count = CustomUser.objects.count()
        mismatch_data = self.register_data.copy()
        mismatch_data['password2'] = 'DifferentPassword123'
        response = self.client.post(
            self.register_url, mismatch_data, format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        # Expected error in password2
        self.assertIn('password2', response.data)
        self.assertEqual(CustomUser.objects.count(), initial_count)

    def test_token_obtain_success(self) -> None:
        """ Testa a obtenção de token bem-sucedida. """
        login_data = {
            'email': self.existing_user.email,
            'password': 'ExistingPassword123'
        }
        response = self.client.post(self.token_url, login_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('access', response.data)
        self.assertIn('refresh', response.data)
        self.assertTrue(response.data['access'])

    def test_token_obtain_fail_wrong_password(self) -> None:
        """ Testa a falha na obtenção de token com senha incorreta. """
        wrong_pw_data = {
            'email': self.existing_user.email, 'password': 'Wrong'
        }
        response_pw = self.client.post(
            self.token_url, wrong_pw_data, format='json'
        )
        self.assertEqual(response_pw.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertIn('detail', response_pw.data)

    def test_token_obtain_fail_nonexistent_user(self) -> None:
        """ Testa a falha na obtenção de token com usuário inexistente. """
        non_user_data = {'email': 'nosuch@e.com', 'password': 'pw'}
        response = self.client.post(
            self.token_url, non_user_data, format='json'
        )
        self.assertEqual(
            response.status_code, status.HTTP_401_UNAUTHORIZED
        )
        self.assertIn('detail', response.data)


# --- Profile and Password Change Tests ---
class ProfileAPITests(BaseAPITestCase):
    """ Testes para perfil e alteração de senha. """
    user: CustomUser
    password: str
    access_token: str

    def setUp(self) -> None:
        """ Cria usuário e obtém token para os testes. """
        self.password = 'TestPassword123'
        self.user = create_test_user(
            'profileuser', 'profile@example.com', self.password
        )
        tokens = self._get_jwt_tokens_for_user(self.user.email, self.password)
        self.access_token = tokens['access']
        self.profile_url = reverse('capyExtended:profile')
        self.change_password_url = reverse('capyExtended:change-password')

    def test_get_profile_success(self) -> None:
        """ Testa visualização de perfil com sucesso (autenticado). """
        self._authenticate_client(self.access_token)
        response = self.client.get(self.profile_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['email'], self.user.email)
        self.assertFalse(response.data['email_confirmed'])

    def test_get_profile_fail_unauthenticated(self) -> None:
        """ Testa falha na visualização de perfil sem autenticação. """
        self._clear_authentication()
        response_unauth = self.client.get(self.profile_url)
        self.assertEqual(
            response_unauth.status_code, status.HTTP_401_UNAUTHORIZED
        )

    def test_update_profile_patch_success(self) -> None:
        """ Testa atualização parcial (PATCH) do perfil com sucesso. """
        self._authenticate_client(self.access_token)
        update_data = {'first_name': 'Profile Updated'}
        response = self.client.patch(
            self.profile_url, update_data, format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['first_name'], 'Profile Updated')
        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, 'Profile Updated')

    def test_update_profile_put_success(self) -> None:
        """
        Verifica se um usuário autenticado consegue atualizar com PUT.
        """
        self._authenticate_client(self.access_token)
        # Data for full update:
        # PUT usually requires all editable fields
        update_data = {
            'first_name': 'Profile PUT',
            'last_name': 'Test PUT',
            'username': self.user.username,  # <-- Adicionar username atual
            'email': self.user.email,       # <-- Add current email
            # profile_image is optional, no need to include if not changing
        }
        response = self.client.put(
            self.profile_url, update_data, format='json'
        )

        # The rest of the assertions remain the same:
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['first_name'], 'Profile PUT')
        self.assertEqual(response.data['last_name'], 'Test PUT')

        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, 'Profile PUT')
        self.assertEqual(self.user.last_name, 'Test PUT')

    def test_update_profile_fail_unauthenticated(self) -> None:
        """ Testa falha na atualização de perfil sem autenticação. """
        self._clear_authentication()
        update_data = {'first_name': 'Failing Update'}
        response_unauth = self.client.patch(
            self.profile_url, update_data, format='json'
        )
        self.assertEqual(
            response_unauth.status_code, status.HTTP_401_UNAUTHORIZED
        )

    def test_change_password_success(self) -> None:
        """ Testa alteração de senha bem-sucedida. """
        self._authenticate_client(self.access_token)
        new_password = "NewSecurePassword456!"
        data_ok = {
            "old_password": self.password,
            "new_password1": new_password, "new_password2": new_password
        }
        response_ok = self.client.put(
            self.change_password_url, data_ok, format='json'
        )
        self.assertEqual(response_ok.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(new_password))

        # Check login with new password
        login_response = self._get_jwt_tokens_for_user(
            self.user.email, new_password
        )
        self.assertIn('access', login_response)

    def test_change_password_fail_wrong_old(self) -> None:
        """ Testa falha na alteração com senha antiga incorreta. """
        self._authenticate_client(self.access_token)
        data_wrong_old = {
            "old_password": "WRONG_OLD_PASSWORD",
            "new_password1": "AnotherNew",
            "new_password2": "AnotherNew",
        }
        response_wrong_old = self.client.put(
            self.change_password_url, data_wrong_old, format='json'
        )
        self.assertEqual(
            response_wrong_old.status_code, status.HTTP_400_BAD_REQUEST
        )
        self.assertIn('old_password', response_wrong_old.data)

    def test_change_password_fail_mismatch(self) -> None:
        """ Testa falha na alteração com novas senhas não coincidentes. """
        self._authenticate_client(self.access_token)
        data_mismatch = {
            "old_password": self.password,
            "new_password1": "AnotherNew",
            "new_password2": "MISMATCH",
        }
        response_mismatch = self.client.put(
            self.change_password_url, data_mismatch, format='json'
        )
        self.assertEqual(
            response_mismatch.status_code, status.HTTP_400_BAD_REQUEST
        )
        self.assertIn('new_password2', response_mismatch.data)

    def test_change_password_fail_unauthenticated(self) -> None:
        """ Testa falha na alteração sem autenticação. """
        self._clear_authentication()
        data_ok = {
            "old_password": self.password,
            "new_password1": "NewSecurePassword456!",
            "new_password2": "NewSecurePassword456!",
        }
        response_unauth = self.client.put(
            self.change_password_url, data_ok, format='json'
        )
        self.assertEqual(
            response_unauth.status_code, status.HTTP_401_UNAUTHORIZED
        )


# --- Item Tests ---
class ItemAPITests(BaseAPITestCase):
    """ Testes para os endpoints de Itens. """
    # Type hints
    user_a: CustomUser
    user_b: CustomUser
    access_token_a: str
    access_token_b: str
    item_pa: Item
    item_pb: Item
    item_ra: Item
    item_rb: Item
    public_list_url: str
    restricted_list_url: str

    @classmethod
    def setUpTestData(cls) -> None:
        """ Cria usuários e itens para testes. """
        cls.public_list_url = reverse('capyExtended:public-item-list')
        cls.restricted_list_url = reverse('capyExtended:restricted-item-list')
        cls.user_a = create_test_user(
            'itemuser_a', 'item_a@example.com',
            'UserAPassword1', confirmed=True
        )
        cls.user_b = create_test_user(
            'itemuser_b', 'item_b@example.com',
            'UserBPassword1', confirmed=False
        )
        cls.item_pa = Item.objects.create(
            owner=cls.user_a, title="Public A Search", is_public=True
        )
        cls.item_pb = Item.objects.create(
            owner=cls.user_b, title="Public B Search", is_public=True
        )
        cls.item_ra = Item.objects.create(
            owner=cls.user_a, title="Restricted A", is_public=False
        )
        cls.item_rb = Item.objects.create(
            owner=cls.user_b, title="Restricted B", is_public=False
        )

    def setUp(self) -> None:
        """ Obtém tokens para usuários. """
        tokens_a = self._get_jwt_tokens_for_user(
            self.user_a.email, 'UserAPassword1'
        )
        tokens_b = self._get_jwt_tokens_for_user(
            self.user_b.email, 'UserBPassword1'
        )
        self.access_token_a = tokens_a['access']
        self.access_token_b = tokens_b['access']

    def test_list_public_items_unauthenticated(self) -> None:
        """ Testa listagem pública sem auth e conteúdo. """
        response = self.client.get(self.public_list_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 2)
        titles = [item['title'] for item in response.data['results']]
        self.assertCountEqual(titles, [self.item_pa.title, self.item_pb.title])

    def test_list_public_items_filtering(self) -> None:
        """ Testa filtro por dono na lista pública. """
        url_owner_a = f"{self.public_list_url}?owner={self.user_a.id}"
        response_owner_a = self.client.get(url_owner_a)
        self.assertEqual(response_owner_a.status_code, status.HTTP_200_OK)
        self.assertEqual(response_owner_a.data['count'], 1)
        self.assertEqual(
            response_owner_a.data['results'][0]['title'], self.item_pa.title
        )

    def test_list_public_items_search(self) -> None:
        """ Testa busca na lista pública. """
        url_search = f"{self.public_list_url}?search=Search"
        response_search = self.client.get(url_search)
        self.assertEqual(response_search.status_code, status.HTTP_200_OK)
        self.assertEqual(response_search.data['count'], 2)

    def test_list_public_items_ordering(self) -> None:
        """ Testa ordenação na lista pública. """
        url_order = f"{self.public_list_url}?ordering=title"
        response_order = self.client.get(url_order)
        self.assertEqual(response_order.status_code, status.HTTP_200_OK)
        titles_ordered = [
            item['title'] for item in response_order.data['results']
        ]
        self.assertEqual(titles_ordered,
                         [self.item_pa.title, self.item_pb.title])

    def test_create_item_success(self) -> None:
        """ Testa criação de item com sucesso (autenticado). """
        self._authenticate_client(self.access_token_a)
        item_data_ok = {'title': 'New Item By A'}
        response_ok = self.client.post(
            self.public_list_url, item_data_ok, format='json'
        )
        self.assertEqual(response_ok.status_code, status.HTTP_201_CREATED)
        item_exists = Item.objects.filter(
            title='New Item By A', owner=self.user_a
        ).exists()
        self.assertTrue(item_exists)

    def test_create_item_fail_unauthenticated(self) -> None:
        """ Testa falha na criação de item sem autenticação. """
        item_data = {'title': 'Fail Item'}
        response_unauth = self.client.post(
            self.public_list_url, item_data, format='json'
        )
        self.assertEqual(
            response_unauth.status_code, status.HTTP_401_UNAUTHORIZED
        )

    def test_list_restricted_items_success_confirmed(self) -> None:
        """ Testa sucesso ao listar restritos (autenticado e confirmado). """
        self._authenticate_client(self.access_token_a)  # User A confirmado
        response_ok = self.client.get(self.restricted_list_url)
        self.assertEqual(response_ok.status_code, status.HTTP_200_OK)
        self.assertEqual(response_ok.data['count'], 2)  # RA1, RB1

    def test_list_restricted_items_fail_unconfirmed(self) -> None:
        """ Testa falha ao listar restritos (autenticado, não confirmado). """
        self._authenticate_client(self.access_token_b)  # User B não confirmado
        response_unconf = self.client.get(self.restricted_list_url)
        self.assertEqual(
            response_unconf.status_code, status.HTTP_403_FORBIDDEN
        )

    def test_list_restricted_items_fail_unauthenticated(self) -> None:
        """ Testa falha ao listar restritos (não autenticado). """
        self._clear_authentication()
        response_unauth = self.client.get(self.restricted_list_url)
        self.assertEqual(
            response_unauth.status_code, status.HTTP_401_UNAUTHORIZED
        )

    def test_list_restricted_items_filtering(self) -> None:
        """ Testa filtro por dono na lista restrita. """
        self._authenticate_client(self.access_token_a)  # User A confirmado
        url_owner_b = f"{self.restricted_list_url}?owner={self.user_b.id}"
        response_owner_b = self.client.get(url_owner_b)
        self.assertEqual(response_owner_b.status_code, status.HTTP_200_OK)
        self.assertEqual(response_owner_b.data['count'], 1)
        self.assertEqual(
            response_owner_b.data['results'][0]['title'], self.item_rb.title
        )


# --- Email Confirmation Tests ---
class EmailConfirmationAPITests(BaseAPITestCase):
    """ Testes para confirmação de e-mail. """
    # Type hints
    user_unconfirmed: CustomUser
    user_confirmed: CustomUser
    access_token_unconfirmed: str
    access_token_confirmed: str
    request_url: str
    validate_url: str
    password: str

    @classmethod
    def setUpTestData(cls) -> None:
        """ Cria usuários confirmado e não confirmado. """
        cls.password = 'TestPassword123'
        cls.user_unconfirmed = create_test_user(
            'unconfirmed_user', 'unconfirmed@example.com', cls.password,
            confirmed=False
        )
        cls.user_confirmed = create_test_user(
            'confirmed_user', 'confirmed@example.com', cls.password,
            confirmed=True
        )
        cls.request_url = reverse('capyExtended:request-confirmation-email')
        cls.validate_url = reverse('capyExtended:validate-confirmation-email')

    def setUp(self) -> None:
        """ Obtém tokens. """
        tokens_unconfirmed = self._get_jwt_tokens_for_user(
            self.user_unconfirmed.email, self.password
        )
        tokens_confirmed = self._get_jwt_tokens_for_user(
            self.user_confirmed.email, self.password
        )
        self.access_token_unconfirmed = tokens_unconfirmed['access']
        self.access_token_confirmed = tokens_confirmed['access']

    def test_request_token_success(self) -> None:
        """ Testa solicitação de token para usuário não confirmado. """
        self._authenticate_client(self.access_token_unconfirmed)
        response = self.client.post(self.request_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('token', response.data)
        self.user_unconfirmed.refresh_from_db()
        self.assertIsNotNone(self.user_unconfirmed.confirmation_token)

    def test_request_token_fail_if_already_confirmed(self) -> None:
        """ Testa falha ao solicitar token para usuário já confirmado. """
        self._authenticate_client(self.access_token_confirmed)
        response = self.client.post(self.request_url)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_request_token_fail_if_unauthenticated(self) -> None:
        """ Testa falha ao solicitar token sem autenticação. """
        self._clear_authentication()
        response = self.client.post(self.request_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_validate_token_success(self) -> None:
        """ Testa validação bem-sucedida com token correto. """
        self._authenticate_client(self.access_token_unconfirmed)
        # 1. Request/Generate token
        req_resp = self.client.post(self.request_url)
        confirmation_token = req_resp.data['token']
        # 2. Validate
        validation_data = {'token': confirmation_token}
        response = self.client.post(
            self.validate_url, validation_data, format='json'
        )
        # 3. Verify
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.user_unconfirmed.refresh_from_db()
        self.assertTrue(self.user_unconfirmed.email_confirmed)
        self.assertIsNone(self.user_unconfirmed.confirmation_token)

    def test_validate_token_fail_wrong_token(self) -> None:
        """ Testa falha na validação com token errado. """
        # Ensure user has a pending token
        self.user_unconfirmed.confirmation_token = uuid.uuid4()
        self.user_unconfirmed.token_created_at = timezone.now()
        self.user_unconfirmed.save()

        self._authenticate_client(self.access_token_unconfirmed)
        wrong_token = uuid.uuid4()  # Token diferente
        validation_data = {'token': str(wrong_token)}
        response = self.client.post(
            self.validate_url, validation_data, format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('inválido', response.data.get('error', ''))
        self.user_unconfirmed.refresh_from_db()
        self.assertFalse(self.user_unconfirmed.email_confirmed)

    def test_validate_token_already_confirmed_user(self) -> None:
        """ Testa resposta ao validar usuário já confirmado. """
        self._authenticate_client(self.access_token_confirmed)
        validation_data = {'token': str(uuid.uuid4())}
        response = self.client.post(
            self.validate_url, validation_data, format='json'
        )
        # View returns
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn(
            'confirmado anteriormente', response.data.get('message', '')
        )

    def test_validate_token_fail_no_pending_token(self) -> None:
        """ Testa falha ao validar sem token pendente. """
        # Ensure there is no token
        self.user_unconfirmed.confirmation_token = None
        self.user_unconfirmed.save()
        self._authenticate_client(self.access_token_unconfirmed)
        validation_data = {'token': str(uuid.uuid4())}
        response = self.client.post(
            self.validate_url, validation_data, format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('Nenhum processo', response.data.get('error', ''))

    def test_validate_token_fail_unauthenticated(self) -> None:
        """ Testa falha na validação sem autenticação. """
        self._clear_authentication()
        validation_data = {'token': str(uuid.uuid4())}
        response = self.client.post(
            self.validate_url, validation_data, format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
