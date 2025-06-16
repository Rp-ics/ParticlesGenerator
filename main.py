import sys
import random
import json
import imageio
import threading
import time
import numpy as np

from PyQt5.QtWidgets import (
    QApplication, QWidget, QLabel, QVBoxLayout, QHBoxLayout,
    QPushButton, QSlider, QColorDialog, QCheckBox, QComboBox,
    QSpinBox, QFileDialog, QMessageBox, QGroupBox
)
from PyQt5.QtCore import Qt, QTimer, QThread, pyqtSignal
from PyQt5.QtGui import QPainter, QColor, QPixmap, QPalette


class Particle:
    def __init__(self, width, height, life, gravity, fade,
                 color=None, direction="Random",
                 size_min=1, size_max=5,
                 vx_min=-5, vx_max=5,
                 vy_min=-5, vy_max=5,
                 wind=0):
        self.width = width
        self.height = height
        self.life = life
        self.gravity = gravity
        self.fade = fade
        self.color = color if color else QColor(random.randint(0, 255),
                                                random.randint(0, 255),
                                                random.randint(0, 255))
        self.size = random.randint(size_min, size_max)
        self.x = random.uniform(0, width)
        self.y = random.uniform(0, height)
        self.vx = random.uniform(vx_min, vx_max) + wind
        self.vy = random.uniform(vy_min, vy_max)
        self.alpha = 255
        self.direction = direction

    def update(self):
        self.vy += self.gravity
        self.x += self.vx
        self.y += self.vy
        self.life -= 1
        self.alpha = max(0, int(255 * self.life / 100))

    def get_color(self):
        c = QColor(self.color)
        c.setAlpha(self.alpha)
        return c


class GifRecorder(QThread):
    finished = pyqtSignal(list)  # Emits frames when done

    def __init__(self, parent=None):
        super().__init__(parent)
        self.frames = []

    def run(self):
        for _ in range(300):  # ~5 seconds at 60 FPS
            time.sleep(1 / 60)
            self.frames.append(np.zeros((400, 600, 4), dtype=np.uint8))  # Placeholder frame
        self.finished.emit(self.frames)


class ParticleGenerator(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Particle Generator - Final Edition")
        self.canvas_width = 600
        self.canvas_height = 400
        self.resize(self.canvas_width + 350, self.canvas_height)

        self.particles = []
        self.selected_color = QColor(255, 255, 255)
        self.bg_color = QColor(25, 25, 25)

        self.timer = QTimer()
        self.timer.timeout.connect(self.update_particles)

        self.recording = False
        self.frames = []

        self.init_ui()

    def init_ui(self):
        main_layout = QHBoxLayout(self)

        # Canvas to draw particles on
        self.canvas = QLabel()
        self.canvas.setFixedSize(self.canvas_width, self.canvas_height)
        self.setStyleSheet(f"background-color: {self.bg_color.name()};")
        main_layout.addWidget(self.canvas)

        controls = QVBoxLayout()
        main_layout.addLayout(controls)

        # --- PARTICLE SETTINGS ---
        particles_group = QGroupBox("Particle Settings")
        particles_layout = QVBoxLayout()

        def add_slider(label_text, min_val, max_val, default, scale=1.0):
            container = QHBoxLayout()
            label = QLabel(label_text)
            slider = QSlider(Qt.Horizontal)
            slider.setRange(min_val, max_val)
            slider.setValue(default)
            value_label = QLabel(f"{default * scale:.2f}")
            slider.valueChanged.connect(lambda val: value_label.setText(f"{val * scale:.2f}"))
            container.addWidget(label)
            container.addWidget(slider)
            container.addWidget(value_label)
            particles_layout.addLayout(container)
            return slider

        def add_spinbox(label_text, min_val, max_val, default):
            container = QHBoxLayout()
            label = QLabel(label_text)
            spinbox = QSpinBox()
            spinbox.setRange(min_val, max_val)
            spinbox.setValue(default)
            value_label = QLabel(str(default))
            spinbox.valueChanged.connect(lambda val: value_label.setText(str(val)))
            container.addWidget(label)
            container.addWidget(spinbox)
            container.addWidget(value_label)
            particles_layout.addLayout(container)
            return spinbox

        self.num_particles_slider = add_slider("Number of Particles", 1, 1000, 100)
        self.gravity_slider = add_slider("Gravity", 0, 50, 10, 0.1)
        self.life_slider = add_slider("Life (Frames)", 1, 500, 100)
        self.fade_slider = add_slider("Fade Speed", 1, 100, 50, 0.01)
        self.vx_min_spin = add_spinbox("Velocity X Min (x0.1)", -100, 100, -50)
        self.vx_max_spin = add_spinbox("Velocity X Max (x0.1)", -100, 100, 50)
        self.vy_min_spin = add_spinbox("Velocity Y Min (x0.1)", -100, 100, -50)
        self.vy_max_spin = add_spinbox("Velocity Y Max (x0.1)", -100, 100, 50)
        self.wind_spin = add_spinbox("Wind (x0.1)", -50, 50, 0)
        self.size_min_spin = add_spinbox("Size Min", 1, 50, 2)
        self.size_max_spin = add_spinbox("Size Max", 1, 50, 5)

        direction_container = QHBoxLayout()
        direction_label = QLabel("Direction")
        self.direction_combo = QComboBox()
        self.direction_combo.addItems(["Random", "Up", "Down", "Left", "Right"])
        direction_container.addWidget(direction_label)
        direction_container.addWidget(self.direction_combo)
        particles_layout.addLayout(direction_container)

        self.color_button = QPushButton("Select Color")
        self.color_button.clicked.connect(self.choose_color)
        particles_layout.addWidget(self.color_button)

        self.multicolor_checkbox = QCheckBox("Multicolor")
        self.multicolor_checkbox.setToolTip("Each particle will have a random color")
        self.multicolor_checkbox.stateChanged.connect(self.multicolor_changed)
        particles_layout.addWidget(self.multicolor_checkbox)

        self.reset_color_checkbox = QCheckBox("Reset Color (White)")
        self.reset_color_checkbox.setToolTip("All particles will be white")
        self.reset_color_checkbox.stateChanged.connect(self.reset_color_changed)
        particles_layout.addWidget(self.reset_color_checkbox)

        particles_group.setLayout(particles_layout)
        controls.addWidget(particles_group)

        # --- SIMULATION CONTROL ---
        sim_group = QGroupBox("Simulation Control")
        sim_layout = QVBoxLayout()

        self.start_button = QPushButton("Start Simulation")
        self.start_button.clicked.connect(self.start_simulation)
        sim_layout.addWidget(self.start_button)

        self.stop_button = QPushButton("Stop Simulation")
        self.stop_button.clicked.connect(self.stop_simulation)
        self.stop_button.setEnabled(False)
        sim_layout.addWidget(self.stop_button)

        self.save_img_button = QPushButton("Save Image as PNG")
        self.save_img_button.clicked.connect(self.save_image)
        sim_layout.addWidget(self.save_img_button)

        self.save_params_button = QPushButton("Save Parameters as JSON")
        self.save_params_button.clicked.connect(self.save_parameters)
        sim_layout.addWidget(self.save_params_button)

        self.load_params_button = QPushButton("Load Parameters from JSON")
        self.load_params_button.clicked.connect(self.load_parameters)
        sim_layout.addWidget(self.load_params_button)

        self.record_gif_button = QPushButton("Record GIF (5s)")
        self.record_gif_button.clicked.connect(self.record_gif)
        sim_layout.addWidget(self.record_gif_button)

        sim_group.setLayout(sim_layout)
        controls.addWidget(sim_group)

        # --- CANVAS OPTIONS ---
        misc_group = QGroupBox("Canvas Options")
        misc_layout = QVBoxLayout()

        self.bg_color_button = QPushButton("Set Background Color")
        self.bg_color_button.clicked.connect(self.choose_bg_color)
        misc_layout.addWidget(self.bg_color_button)

        misc_group.setLayout(misc_layout)
        controls.addWidget(misc_group)

    def choose_color(self):
        color = QColorDialog.getColor()
        if color.isValid():
            self.selected_color = color
            self.reset_color_checkbox.setChecked(False)
            self.multicolor_checkbox.setChecked(False)

    def choose_bg_color(self):
        color = QColorDialog.getColor()
        if color.isValid():
            self.bg_color = color
            self.setStyleSheet(f"background-color: {color.name()};")

    def multicolor_changed(self, state):
        if state == Qt.Checked:
            self.reset_color_checkbox.setChecked(False)

    def reset_color_changed(self, state):
        if state == Qt.Checked:
            self.multicolor_checkbox.setChecked(False)
            self.selected_color = QColor(255, 255, 255)

    def start_simulation(self):
        num = self.num_particles_slider.value()
        gravity = self.gravity_slider.value() / 10.0
        life = self.life_slider.value()
        fade = self.fade_slider.value() / 100.0
        vx_min = self.vx_min_spin.value() / 10.0
        vx_max = self.vx_max_spin.value() / 10.0
        vy_min = self.vy_min_spin.value() / 10.0
        vy_max = self.vy_max_spin.value() / 10.0
        wind = self.wind_spin.value() / 10.0
        size_min = self.size_min_spin.value()
        size_max = self.size_max_spin.value()
        direction = self.direction_combo.currentText()

        self.particles.clear()
        for _ in range(num):
            if self.multicolor_checkbox.isChecked():
                color = QColor(random.randint(0, 255), random.randint(0, 255), random.randint(0, 255))
            elif self.reset_color_checkbox.isChecked():
                color = QColor(255, 255, 255)
            else:
                color = self.selected_color

            particle = Particle(
                width=self.canvas_width, height=self.canvas_height,
                life=life, gravity=gravity, fade=fade,
                color=color, direction=direction,
                size_min=size_min, size_max=size_max,
                vx_min=vx_min, vx_max=vx_max,
                vy_min=vy_min, vy_max=vy_max,
                wind=wind
            )
            self.particles.append(particle)

        self.timer.start(16)
        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)

    def stop_simulation(self):
        self.timer.stop()
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)

    def update_particles(self):
        alive = []
        for p in self.particles:
            p.update()
            if p.life > 0:
                alive.append(p)
        self.particles = alive

        if not self.particles:
            self.stop_simulation()

        pixmap = QPixmap(self.canvas_width, self.canvas_height)
        pixmap.fill(self.bg_color)
        painter = QPainter(pixmap)
        for p in self.particles:
            painter.setBrush(p.get_color())
            painter.setPen(Qt.NoPen)
            painter.drawEllipse(int(p.x), int(p.y), p.size, p.size)
        painter.end()
        self.canvas.setPixmap(pixmap)

        if self.recording:
            frame = pixmap.toImage()
            ptr = frame.bits()
            ptr.setsize(frame.byteCount())
            arr = np.array(ptr).reshape(frame.height(), frame.width(), 4)
            self.frames.append(arr.copy())

    def save_image(self):
        if not self.canvas.pixmap():
            QMessageBox.warning(self, "Warning", "No image to save.")
            return
        fname, _ = QFileDialog.getSaveFileName(self, "Save Image", "", "PNG Files (*.png)")
        if fname:
            self.canvas.pixmap().save(fname, "PNG")

    def save_parameters(self):
        params = {
            "num_particles": self.num_particles_slider.value(),
            "gravity": self.gravity_slider.value() / 10.0,
            "life": self.life_slider.value(),
            "fade": self.fade_slider.value() / 100.0,
            "vx_min": self.vx_min_spin.value() / 10.0,
            "vx_max": self.vx_max_spin.value() / 10.0,
            "vy_min": self.vy_min_spin.value() / 10.0,
            "vy_max": self.vy_max_spin.value() / 10.0,
            "wind": self.wind_spin.value() / 10.0,
            "size_min": self.size_min_spin.value(),
            "size_max": self.size_max_spin.value(),
            "direction": self.direction_combo.currentText(),
            "color": (self.selected_color.red(), self.selected_color.green(), self.selected_color.blue()),
            "multicolor": self.multicolor_checkbox.isChecked(),
            "reset_color": self.reset_color_checkbox.isChecked(),
        }
        fname, _ = QFileDialog.getSaveFileName(self, "Save Parameters", "", "JSON Files (*.json)")
        if fname:
            try:
                with open(fname, "w") as f:
                    json.dump(params, f, indent=4)
                QMessageBox.information(self, "Success", "Parameters saved.")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to save: {e}")

    def load_parameters(self):
        fname, _ = QFileDialog.getOpenFileName(self, "Load Parameters", "", "JSON Files (*.json)")
        if fname:
            try:
                with open(fname, 'r') as f:
                    params = json.load(f)
                self.num_particles_slider.setValue(params["num_particles"])
                self.gravity_slider.setValue(int(params["gravity"] * 10))
                self.life_slider.setValue(params["life"])
                self.fade_slider.setValue(int(params["fade"] * 100))
                self.vx_min_spin.setValue(int(params["vx_min"] * 10))
                self.vx_max_spin.setValue(int(params["vx_max"] * 10))
                self.vy_min_spin.setValue(int(params["vy_min"] * 10))
                self.vy_max_spin.setValue(int(params["vy_max"] * 10))
                self.wind_spin.setValue(int(params["wind"] * 10))
                self.size_min_spin.setValue(params["size_min"])
                self.size_max_spin.setValue(params["size_max"])
                index = self.direction_combo.findText(params["direction"])
                if index >= 0:
                    self.direction_combo.setCurrentIndex(index)
                r, g, b = params["color"]
                self.selected_color = QColor(r, g, b)
                self.multicolor_checkbox.setChecked(params.get("multicolor", False))
                self.reset_color_checkbox.setChecked(params.get("reset_color", False))
                QMessageBox.information(self, "Success", "Parameters loaded.")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to load: {e}")

    def record_gif(self):
        if self.recording:
            QMessageBox.warning(self, "Warning", "Already recording a GIF.")
            return
        self.frames.clear()
        self.recording = True
        self.start_simulation()

        self.gif_recorder = GifRecorder(self)
        self.gif_recorder.finished.connect(self.save_gif_frames)
        self.gif_recorder.start()

    def save_gif_frames(self, frames):
        self.recording = False
        fname, _ = QFileDialog.getSaveFileName(self, "Save GIF", "", "GIF Files (*.gif)")
        if fname and self.frames:
            try:
                imageio.mimsave(fname, self.frames, duration=1 / 60)
                QMessageBox.information(self, "Success", "GIF saved successfully.")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to save GIF: {e}")


def set_dark_theme(app):
    app.setStyle("Fusion")
    palette = QPalette()
    palette.setColor(QPalette.Window, QColor(53, 53, 53))
    palette.setColor(QPalette.WindowText, Qt.white)
    palette.setColor(QPalette.Base, QColor(25, 25, 25))
    palette.setColor(QPalette.AlternateBase, QColor(53, 53, 53))
    palette.setColor(QPalette.ToolTipBase, Qt.white)
    palette.setColor(QPalette.ToolTipText, Qt.white)
    palette.setColor(QPalette.Text, Qt.white)
    palette.setColor(QPalette.Button, QColor(53, 53, 53))
    palette.setColor(QPalette.ButtonText, Qt.white)
    palette.setColor(QPalette.BrightText, Qt.red)
    palette.setColor(QPalette.Link, QColor(42, 130, 218))
    palette.setColor(QPalette.Highlight, QColor(42, 130, 218))
    palette.setColor(QPalette.HighlightedText, Qt.black)
    app.setPalette(palette)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    set_dark_theme(app)
    window = ParticleGenerator()
    window.show()
    sys.exit(app.exec_())