"""
Credential Service - Secure storage and retrieval of platform credentials
Uses AES-256-GCM encryption for sensitive data
"""

import base64
import json
from typing import Dict, Optional

from Crypto.Cipher import AES
from Crypto.Random import get_random_bytes

from src.core.config import settings
from src.services.supabase_client import supabase_client


class CredentialService:
	"""
	Secure credential management with AES-256-GCM encryption.

	All credentials are encrypted before storage and decrypted on retrieval.
	Uses Supabase with Row Level Security for additional protection.
	"""

	def __init__(self):
		self.key = settings.get_encryption_key()

	def _encrypt(self, plaintext: str) -> tuple[str, str]:
		"""
		Encrypt a string using AES-256-GCM.

		Returns:
		    tuple: (encrypted_data_base64, iv_base64)
		"""
		iv = get_random_bytes(12)  # GCM recommended IV size
		cipher = AES.new(self.key, AES.MODE_GCM, nonce=iv)
		ciphertext, tag = cipher.encrypt_and_digest(plaintext.encode('utf-8'))

		# Combine ciphertext and tag
		encrypted_data = ciphertext + tag

		return (base64.b64encode(encrypted_data).decode('utf-8'), base64.b64encode(iv).decode('utf-8'))

	def _decrypt(self, encrypted_data_b64: str, iv_b64: str) -> str:
		"""
		Decrypt data using AES-256-GCM.

		Args:
		    encrypted_data_b64: Base64 encoded ciphertext + tag
		    iv_b64: Base64 encoded initialization vector

		Returns:
		    Decrypted plaintext string
		"""
		encrypted_data = base64.b64decode(encrypted_data_b64)
		iv = base64.b64decode(iv_b64)

		# Split ciphertext and tag (tag is last 16 bytes)
		ciphertext = encrypted_data[:-16]
		tag = encrypted_data[-16:]

		cipher = AES.new(self.key, AES.MODE_GCM, nonce=iv)
		plaintext = cipher.decrypt_and_verify(ciphertext, tag)

		return plaintext.decode('utf-8')

	async def store_credential(
		self, user_id: str, platform: str, username: str, password: str, credential_type: str = 'login'
	) -> Dict:
		"""
		Encrypt and store credentials in Supabase.

		Args:
		    user_id: The user's UUID
		    platform: Platform name (e.g., 'linkedin', 'indeed')
		    username: Username or email
		    password: Password
		    credential_type: Type of credential ('login', 'oauth', 'api_key')

		Returns:
		    The stored credential record (without sensitive data)
		"""
		# Encrypt username and password separately
		encrypted_username, iv_username = self._encrypt(username)
		encrypted_password, iv_password = self._encrypt(password)

		# Combine IVs (both are needed for decryption)
		combined_iv = json.dumps({'u': iv_username, 'p': iv_password})

		data = {
			'user_id': user_id,
			'platform': platform.lower(),
			'credential_type': credential_type,
			'encrypted_username': encrypted_username,
			'encrypted_password': encrypted_password,
			'encryption_iv': combined_iv,
			'is_valid': True,
		}

		# Upsert (update if exists, insert if not)
		response = supabase_client.table('platform_credentials').upsert(data, on_conflict='user_id,platform').execute()

		if response.data:
			# Return without sensitive data
			return {
				'id': response.data[0]['id'],
				'platform': platform,
				'credential_type': credential_type,
				'created_at': response.data[0]['created_at'],
			}
		return None

	async def get_credential(self, user_id: str, platform: str) -> Optional[Dict[str, str]]:
		"""
		Retrieve and decrypt credentials for a platform.

		Args:
		    user_id: The user's UUID
		    platform: Platform name

		Returns:
		    Dict with 'username' and 'password', or None if not found
		"""
		response = (
			supabase_client.table('platform_credentials')
			.select('encrypted_username, encrypted_password, encryption_iv, is_valid')
			.eq('user_id', user_id)
			.eq('platform', platform.lower())
			.single()
			.execute()
		)

		if not response.data:
			return None

		if not response.data.get('is_valid'):
			return None

		# Parse IVs
		ivs = json.loads(response.data['encryption_iv'])

		# Decrypt
		username = self._decrypt(response.data['encrypted_username'], ivs['u'])
		password = self._decrypt(response.data['encrypted_password'], ivs['p'])

		# Update last_used timestamp
		supabase_client.table('platform_credentials').update({'last_used': 'now()'}).eq('user_id', user_id).eq(
			'platform', platform.lower()
		).execute()

		return {'username': username, 'password': password}

	async def delete_credential(self, user_id: str, platform: str) -> bool:
		"""Delete stored credentials for a platform."""
		response = (
			supabase_client.table('platform_credentials')
			.delete()
			.eq('user_id', user_id)
			.eq('platform', platform.lower())
			.execute()
		)

		return len(response.data) > 0 if response.data else False

	async def invalidate_credential(self, user_id: str, platform: str) -> bool:
		"""Mark credentials as invalid (e.g., after failed login)."""
		response = (
			supabase_client.table('platform_credentials')
			.update({'is_valid': False})
			.eq('user_id', user_id)
			.eq('platform', platform.lower())
			.execute()
		)

		return len(response.data) > 0 if response.data else False

	async def list_platforms(self, user_id: str) -> list:
		"""List all platforms with stored credentials for a user."""
		response = (
			supabase_client.table('platform_credentials')
			.select('platform, credential_type, is_valid, last_used, created_at')
			.eq('user_id', user_id)
			.execute()
		)

		return response.data or []


# Singleton instance
credential_service = CredentialService()
