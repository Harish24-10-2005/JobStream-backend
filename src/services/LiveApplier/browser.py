"""
Browser management for the LiveApplier service.

Handles:
- Browser instance lifecycle (create, reuse, cleanup)
- Screenshot streaming loop
- Remote interaction handling (click, type, scroll)
"""

import asyncio
import logging
from typing import TYPE_CHECKING, Any, Optional

from .models import BrowserArgs, ScreenshotConfig

if TYPE_CHECKING:
	from browser_use import Browser

logger = logging.getLogger(__name__)


class BrowserManager:
	"""
	Manages browser lifecycle and screenshot streaming.

	Features:
	- Lazy browser initialization
	- Docker-compatible Chrome configuration
	- Background screenshot capture loop
	- Remote interaction support
	"""

	def __init__(self, session_id: str, event_emitter: Any):
		"""
		Initialize browser manager.

		Args:
		    session_id: Unique session identifier
		    event_emitter: Callable to emit events (EventType, message, data)
		"""
		self.session_id = session_id
		self._emit = event_emitter
		self._browser: Optional['Browser'] = None
		self._browser_session = None
		self._screenshot_task: Optional[asyncio.Task] = None
		self._is_running = False

	async def get_browser(self) -> 'Browser':
		"""
		Get or create a browser instance.

		Returns:
		    Configured Browser instance
		"""
		from browser_use import Browser

		# Always create new browser for now to avoid state issues
		if self._browser:
			try:
				await self._browser.close()
			except Exception:
				pass

		# Docker/cloud-compatible Chrome args
		chrome_args = BrowserArgs.DOCKER_ARGS.copy()

		# Use simple Browser constructor compatible with 0.11.x
		self._browser = Browser()

		logger.info(f'Browser created for session {self.session_id}')
		return self._browser

	def set_browser_session(self, session: Any):
		"""Set the browser session from the agent for screenshots."""
		self._browser_session = session

	def start_screenshot_loop(self):
		"""Start the background screenshot streaming task."""
		self._is_running = True
		self._screenshot_task = asyncio.create_task(self._screenshot_loop())
		logger.debug(f'Screenshot loop started for session {self.session_id}')

	def stop_screenshot_loop(self):
		"""Stop the screenshot streaming task."""
		self._is_running = False
		if self._screenshot_task:
			self._screenshot_task.cancel()
			logger.debug(f'Screenshot loop stopped for session {self.session_id}')

	async def _screenshot_loop(self):
		"""Capture and stream screenshots at configured FPS."""
		from src.api.websocket import EventType

		frame_count = 0
		error_count = 0

		# Wait for browser session to be available
		wait_count = 0
		max_wait = 60  # Max 30 seconds
		while self._is_running and not self._browser_session and wait_count < max_wait:
			wait_count += 1
			if wait_count % 10 == 1:
				logger.debug(f'Waiting for browser_session... ({wait_count}/{max_wait})')
			await asyncio.sleep(0.5)

		if not self._browser_session:
			logger.warning('Screenshot loop exiting - no session available after timeout')
			return

		# Wait for browser to fully initialize
		logger.info('Browser session available! Waiting for page to load...')
		await asyncio.sleep(3.0)

		while self._is_running:
			try:
				page = await self._get_active_page()

				if page:
					screenshot_b64 = await page.screenshot(format=ScreenshotConfig.FORMAT, quality=ScreenshotConfig.QUALITY)

					frame_count += 1
					if frame_count <= 3 or frame_count % 50 == 0:
						logger.info(f'Screenshot frame #{frame_count}, size={len(screenshot_b64)}')

					await self._emit(
						EventType.BROWSER_SCREENSHOT,
						'Browser screenshot',
						{'screenshot': screenshot_b64, 'format': ScreenshotConfig.FORMAT},
					)
					error_count = 0
				elif error_count < 5:
					logger.debug('No page available for screenshot')
					error_count += 1

			except Exception as e:
				error_count += 1
				if error_count <= 3:
					logger.warning(f'Screenshot error: {e}')

			await asyncio.sleep(ScreenshotConfig.INTERVAL)

		logger.debug(f'Screenshot loop ended, total frames: {frame_count}')

	async def _get_active_page(self):
		"""Get the currently active page from browser session."""
		if not self._browser_session:
			return None

		try:
			page = await self._browser_session.get_current_page()
			if page:
				return page

			# Fallback: get any available page
			pages = await self._browser_session.get_pages()
			if pages:
				return pages[-1]
		except Exception as e:
			logger.debug(f'Failed to get active page: {e}')

		return None

	async def capture_full_page_screenshot(self) -> Optional[str]:
		"""
		Capture a full-page screenshot for draft review.

		Returns:
		    Base64 encoded JPEG screenshot, or None on failure
		"""
		if not self._browser_session:
			return None

		try:
			page = await self._get_active_page()
			if page:
				return await page.screenshot(
					format=ScreenshotConfig.FORMAT,
					quality=ScreenshotConfig.DRAFT_QUALITY,
					full_page=ScreenshotConfig.DRAFT_FULL_PAGE,
				)
		except Exception as e:
			logger.warning(f'Failed to capture full-page screenshot: {e}')

		return None

	async def perform_interaction(self, interaction: dict):
		"""
		Execute a remote interaction on the active browser page.

		Args:
		    interaction: Dictionary with 'type', 'x', 'y', 'text', etc.
		"""
		if not self._browser_session:
			logger.warning('Interaction ignored: No active browser session')
			return

		try:
			page = await self._get_active_page()
			if not page:
				return

			action_type = interaction.get('type')

			if action_type == 'click':
				x, y = interaction.get('x'), interaction.get('y')
				if x is not None and y is not None:
					logger.debug(f'Remote click at ({x}, {y})')
					await page.mouse.click(x, y)

			elif action_type == 'type':
				text = interaction.get('text', '')
				if text:
					logger.debug(f"Remote type: '{text}'")
					await page.keyboard.type(text)

			elif action_type == 'key':
				key = interaction.get('key', '')
				if key:
					logger.debug(f"Remote key press: '{key}'")
					await page.keyboard.press(key)

			elif action_type == 'scroll':
				delta_y = interaction.get('delta_y', 0)
				if delta_y:
					await page.mouse.wheel(0, delta_y)

		except Exception as e:
			logger.error(f'Failed to perform interaction: {e}')

	async def cleanup(self):
		"""Close browser and cleanup resources."""
		self.stop_screenshot_loop()

		if self._screenshot_task:
			try:
				await self._screenshot_task
			except asyncio.CancelledError:
				pass

		if self._browser:
			try:
				await self._browser.close()
				logger.info(f'Browser closed for session {self.session_id}')
			except Exception as e:
				logger.debug(f'Ignored error closing browser: {e}')
			finally:
				self._browser = None
				self._browser_session = None
