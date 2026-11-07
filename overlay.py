"""Overlay window using PySide6. Draws boxes and labels on a transparent, click-through window.

This module exposes OverlayWindow which can be updated with a list of detections.
"""
from typing import List, Tuple
import ctypes
import sys
import time
import math
from collections import deque
from loguru import logger
from PySide6 import QtCore, QtGui, QtWidgets
import win32con
import win32gui



class OverlayWindow(QtWidgets.QWidget):
	# Signal used to update detections from other threads safely
	update_signal = QtCore.Signal(object, object)

	def __init__(self, parent=None):
		super().__init__(parent)
		self.setWindowFlags(QtCore.Qt.WindowStaysOnTopHint | QtCore.Qt.FramelessWindowHint | QtCore.Qt.Tool)
		self.setAttribute(QtCore.Qt.WA_TranslucentBackground)
		self.setAttribute(QtCore.Qt.WA_ShowWithoutActivating)
		# Make the widget ignore mouse events so it is click-through
		self.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents, True)
		self.detections: List[dict] = []
		self.target_size = (0, 0)
		# automation status displayed on overlay (ON/OFF)
		self._automation_enabled = False
		# connect the cross-thread update signal to internal slot
		try:
			self.update_signal.connect(self._on_update_signal)
		except Exception:
			# ignore if signal connection fails for any reason
			pass

		# Smoothing / trail visualization settings
		self._smoothing_enabled = True
		self._smoothing_alpha = 0.35  # interpolation factor (0..1), higher = snappier
		self._track_timeout = 0.5  # seconds before a track is considered stale
		self._trail_enabled = True
		self._trail_length = 8
		# Internal tracking state: list of tracks (each track is a dict)
		self._tracks: List[dict] = []

	def make_clickthrough(self):
		hwnd = int(self.winId())
		ex_style = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
		ex_style |= win32con.WS_EX_LAYERED | win32con.WS_EX_TRANSPARENT
		win32gui.SetWindowLong(hwnd, win32con.GWL_EXSTYLE, ex_style)

	def update_overlay(self, detections: List[dict], target_size: Tuple[int, int]):
		"""Thread-safe update entrypoint: can be called from detection thread.
		Emits a Qt signal to apply the update on the GUI thread. If emitting
		fails because we're already on the GUI thread, it applies the update directly.
		"""
		try:
			self.update_signal.emit(detections, target_size)
		except RuntimeError:
			# If emitting isn't allowed (already in GUI thread), apply directly
			self.detections = detections
			self.target_size = target_size
			self.update()

	@QtCore.Slot(object, object)
	def _on_update_signal(self, detections: List[dict], target_size: Tuple[int, int]):
		# Apply updates on the GUI thread
		# Update target size
		self.target_size = target_size
		# If smoothing is disabled, apply detections directly
		if not self._smoothing_enabled:
			self.detections = detections
			self.update()
			return

		# Update tracks with incoming detections
		now = time.time()
		used = [False] * len(detections)
		# Helper to compute center
		def center_of(d):
			try:
				x = float(d.get('x', 0))
				y = float(d.get('y', 0))
				w = float(d.get('width', 0))
				h = float(d.get('height', 0))
				return (x + w/2.0, y + h/2.0)
			except Exception:
				return (0.0, 0.0)

		# Try to match incoming detections to existing tracks by nearest center and class
		for tr in self._tracks:
			tr['matched'] = False
		for i, d in enumerate(detections):
			cx, cy = center_of(d)
			best_idx = None
			best_dist = None
			for ti, tr in enumerate(self._tracks):
				# require same class for matching (if present)
				if tr.get('class') and d.get('class') and str(tr.get('class')).lower() != str(d.get('class')).lower():
					continue
				# compute distance to track center
				tcx, tcy = tr.get('cx', 0.0), tr.get('cy', 0.0)
				dist = math.hypot(cx - tcx, cy - tcy)
				if best_dist is None or dist < best_dist:
					best_dist = dist
					best_idx = ti
			# Accept match if within reasonable pixel distance (adaptive threshold)
			if best_idx is not None and best_dist is not None and best_dist < max(40.0, (d.get('width',0) or 0) * 0.6):
				tr = self._tracks[best_idx]
				# Update track by interpolating towards the new detection
				alpha = self._smoothing_alpha
				trx = float(tr.get('x', 0.0))
				try:
					newx = float(d.get('x', 0.0))
					newy = float(d.get('y', 0.0))
					neww = float(d.get('width', 0.0))
					newh = float(d.get('height', 0.0))
				except Exception:
					newx = newy = neww = newh = 0.0
				tr['x'] = trx + (newx - trx) * alpha
				try:
					tr['y'] = float(tr.get('y', 0.0)) + (newy - float(tr.get('y', 0.0))) * alpha
					tr['width'] = float(tr.get('width', 0.0)) + (neww - float(tr.get('width', 0.0))) * alpha
					tr['height'] = float(tr.get('height', 0.0)) + (newh - float(tr.get('height', 0.0))) * alpha
				except Exception:
					tr['y'] = newy
					tr['width'] = neww
					tr['height'] = newh
				# update center for matching
				tr['cx'], tr['cy'] = center_of(tr)
				tr['confidence'] = d.get('confidence', tr.get('confidence'))
				tr['class'] = d.get('class', tr.get('class'))
				tr['last_seen'] = now
				# update trail
				if self._trail_enabled:
					tr['trail'].appendleft((tr['x'] + tr.get('width',0)/2.0, tr['y'] + tr.get('height',0)/2.0))
					if len(tr['trail']) > self._trail_length:
						tr['trail'].pop()
				tr['matched'] = True
				used[i] = True
		# Create tracks for unmatched detections
		for i, d in enumerate(detections):
			if used[i]:
				continue
			try:
				x = float(d.get('x',0.0))
				y = float(d.get('y',0.0))
				w = float(d.get('width',0.0))
				h = float(d.get('height',0.0))
			except Exception:
				x = y = w = h = 0.0
			track = {
				'x': x,
				'y': y,
				'width': w,
				'height': h,
				'class': d.get('class'),
				'confidence': d.get('confidence', 0.0),
				'cx': x + w/2.0,
				'cy': y + h/2.0,
				'last_seen': now,
				'trail': deque(maxlen=self._trail_length)
			}
			if self._trail_enabled:
				track['trail'].appendleft((track['cx'], track['cy']))
			self._tracks.append(track)

		# Remove stale tracks
		self._tracks = [tr for tr in self._tracks if now - tr.get('last_seen', 0) <= self._track_timeout]

		# Expose tracks as detections for painting
		self.detections = [
			{
				'x': tr['x'], 'y': tr['y'], 'width': tr['width'], 'height': tr['height'],
				'class': tr.get('class'), 'confidence': tr.get('confidence', 0.0), 'trail': list(tr.get('trail', []))
			} for tr in self._tracks
		]
		self.update()

	def set_automation_enabled(self, enabled: bool):
		self._automation_enabled = bool(enabled)
		self.update()

	def paintEvent(self, event: QtGui.QPaintEvent):
		painter = QtGui.QPainter(self)
		painter.setRenderHint(QtGui.QPainter.Antialiasing)
		pen = QtGui.QPen(QtGui.QColor(255, 0, 0, 200))
		pen.setWidth(2)
		painter.setPen(pen)
		font = QtGui.QFont("Segoe UI", 10)
		painter.setFont(font)

		w, h = self.target_size
		for d in self.detections:
			# Expect detection with x,y,width,height in pixel coords relative to target_size
			try:
				x = int(d["x"])
				y = int(d["y"])
				ww = int(d["width"])
				hh = int(d["height"])
				cls = str(d.get("class", ""))
				conf = d.get("confidence", 0)
			except Exception:
				continue
			rect = QtCore.QRect(x, y, ww, hh)
			# Draw trails first (if available)
			trail = d.get('trail') or []
			if self._trail_enabled and trail:
				# draw faded circles/rects along the trail
				for idx, (tx, ty) in enumerate(trail):
					alpha = int(200 * (1.0 - (idx / max(1, len(trail)))))
					clr = QtGui.QColor(255, 120, 0, max(24, alpha // 3))
					brush = QtGui.QBrush(clr)
					painter.setBrush(brush)
					r = 6
					painter.drawEllipse(int(tx)-r, int(ty)-r, r*2, r*2)
				# restore pen/brush
				painter.setBrush(QtGui.QBrush())
			# draw the box
			painter.drawRect(rect)
			text = f"{cls} {conf:.2f}" if isinstance(conf, (float, int)) else f"{cls}"
			text_bg = QtGui.QColor(0, 0, 0, 160)
			metrics = painter.fontMetrics()
			tw = metrics.horizontalAdvance(text) + 6
			th = metrics.height() + 2
			# Prefer drawing the label above the box; if it would be off-screen, draw below the box
			if y - th >= 0:
				bg_y = y - th
				text_y = y - 3
			else:
				bg_y = y + hh
				text_y = y + hh + th - 3
			# ensure within widget bounds horizontally
			bg_x = max(0, x)
			if bg_x + tw > self.width():
				bg_x = max(0, self.width() - tw)
			painter.fillRect(bg_x, bg_y, tw, th, text_bg)
			painter.setPen(QtGui.QColor(255, 255, 255))
			painter.drawText(bg_x + 3, text_y, text)

		# Draw automation status at top-left of the overlay
		status_text = "AUTOMATION: ON" if self._automation_enabled else "AUTOMATION: OFF"
		status_color = QtGui.QColor(0, 180, 0) if self._automation_enabled else QtGui.QColor(200, 0, 0)
		metrics = painter.fontMetrics()
		tw = metrics.horizontalAdvance(status_text) + 8
		th = metrics.height() + 6
		# background box
		painter.fillRect(6, 6, tw, th, QtGui.QColor(0, 0, 0, 160))
		painter.setPen(status_color)
		painter.drawText(10, 6 + th - 4, status_text)

