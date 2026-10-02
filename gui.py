# app_GUI.py
import sys
import json
import os
import copy
import io
from collections import Counter
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                             QTabWidget, QPushButton, QFileDialog, QTableWidget,
                             QTableWidgetItem, QHeaderView, QGroupBox, QFormLayout,
                             QLabel, QTextEdit, QDialog, QDialogButtonBox,
                             QDoubleSpinBox, QHBoxLayout, QSplitter, QScrollArea,
                             QSizePolicy, QFrame, QListWidget, QListWidgetItem, QCheckBox,
                             QComboBox, QInputDialog, QMessageBox)
from PyQt6.QtCore import QSettings, QThreadPool, Qt, QLocale, QPointF
from PyQt6.QtGui import QFont, QPainter, QColor, QPen, QBrush, QFontMetrics, QImage

# Assicurati che gli altri due file siano nella stessa cartella
from analysis_logic import analyze_data, classify_pnp, validate_exam
from file_processor import FileProcessor
from reporting import build_text_report, build_html_report
from phase2_dataset import build_validation_dataset

class NerveSelectionDialog(QDialog):
    # Dizionario strutturato per tipo di esame -> Gruppo -> Lista Nervi
    NERVE_DATA = {
        "motor": {
            "Upper limb": [
                "Nervus medianus (wrist)",           # Median (wrist)
                "Nervus medianus (elbow)",          # Median (elbow)
                "Nervus ulnaris (wrist)",            # Ulnar (wrist)
                "Nervus ulnaris (underarm)",           # Ulnar (underarm/axilla)
                "Nervus ulnaris (upper arm)",          # Ulnar (upper arm)
                "Nervus radialis",                       # Radial
                "Nervus circumflexus",                   # Circumflex (nome storico per Axillaris)
                "Nervus axillaris",                      # Axillary
                "Nervus musculocutaneus",                # Musculo-cutaneous
                "Nervus interosseus anterior",           # Anterior interosseous
                "Nervus interosseus posterior"           # Posterior interosseous
            ],
            "Lower limb": [
                "Nervus peroneus (ankle)",        # Peroneal (ankle) - Nota: o N. fibularis
                "Nervus peroneus (knee)",         # Peroneal (knee/popliteal fossa)
                "Nervus tibialis (ankle)",        # Tibial (ankle)
                "Nervus tibialis (knee)",         # Tibial (knee)
                "Nervus femoralis",                      # Femoral
                "Nervus ischiadicus",                    # Sciatic
                "Nervus gluteus inferior"                # Gluteus maximus (il nervo per questo muscolo)
            ]
        },
        "sensory": {
            "Upper limb": [
                "N. medianus - Digitus II - Dexter (wrist)",  # Median-Digit II-Right
                "N. medianus - Digitus II - Sinister (wrist)",# Median-Digit II-Left
                "N. ulnaris - Digitus V - Dexter (wrist)",    # Ulnar-Digit V-Right
                "N. ulnaris - Digitus V - Sinister (wrist)",  # Ulnar-Digit V-Left
                "Nervus cutaneus brachii lateralis",              # Lateral arm skin
                "Nervus cutaneus brachii medialis",               # Medial arm skin
                "Nervus cutaneus antebrachii medialis",           # Medial forearm skin
                "Nervus cutaneus antebrachii lateralis",          # Lateral forearm skin
                "Ramus superficialis nervi radialis"              # Superficial radial
            ],
            "Lower limb": [
                "Nervus suralis - Dexter (lateral leg)",        # Surale-Right
                "Nervus peroneus superficialis (lateral leg)",            # Superior (Superficial) Peroneal
                "Nervus iliohypogastricus (lateral leg)",       # Ileoipogastric
                "Nervus ilioinguinalis (lateral leg)",          # Ileinguinal
                "Nervus genitofemoralis (lateral leg)",         # Genitofemoral
                "Nervus cutaneus femoris lateralis",              # Lateral Cutaneous Nerve of the Thigh
                "Nervus saphenus"                                 # Saphenous Nerve
            ]
        },
        "fwave": {
            "F-Wave Nerves": [
                "Nervus tibialis (knee)",         # Tibial (Knee)
                "Nervus peroneus",           # Peroneal-EDB (Extensor Digitorum Brevis)
                "Nervus medianus (wrist)",           # Median (Wrist)
                "Nervus ulnaris (wrist)"             # Ulnar (Wrist)
            ]
        }
    }

    def __init__(self, nerve_type="motor", parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Select {nerve_type.title()} Nerves to Add")
        self.setMinimumWidth(450)
        self.setMinimumHeight(400)
        
        main_layout = QVBoxLayout(self)
        self.checkboxes = []

        # Recupera i gruppi corretti in base alla chiave (motor, sensory, fwave)
        current_data = self.NERVE_DATA.get(nerve_type, {})

        # Crea dinamicamente i gruppi (Upper/Lower o F-Wave unico)
        for group_name, nerves_list in current_data.items():
            group_box = QGroupBox(group_name)
            group_layout = QVBoxLayout()
            for nerve in nerves_list:
                cb = QCheckBox(nerve)
                self.checkboxes.append(cb)
                group_layout.addWidget(cb)
            group_box.setLayout(group_layout)
            main_layout.addWidget(group_box)

        # Aggiunta scroll area se la lista è lunga (opzionale ma consigliato per liste lunghe)
        if len(self.checkboxes) > 15:
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            content = QWidget()
            content.setLayout(main_layout)
            scroll.setWidget(content)
            # Ricrea il layout principale per contenere la scroll area
            outer_layout = QVBoxLayout(self)
            outer_layout.addWidget(scroll)
            main_layout = outer_layout # Hack per riutilizzare button_box sotto

        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        button_box.button(QDialogButtonBox.StandardButton.Ok).setText("Add Selected")
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        main_layout.addWidget(button_box)
    
    def get_selected_nerves(self):
        return [cb.text() for cb in self.checkboxes if cb.isChecked()]

class ColorSwatch(QWidget):
    # ... (invariato) ...
    def __init__(self, color, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.color = color
        self.setFixedSize(14, 14)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setOpacity(0.1) 
        painter.setBrush(self.color)
        border_color = QColor(self.color)
        border_color.setAlpha(255)
        painter.setPen(QPen(border_color.darker(110), 1))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(self.rect(), 3, 3)
        painter.setOpacity(1.0)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(border_color.darker(110), 1))
        painter.drawRoundedRect(self.rect(), 3, 3)


class PlotterWidget(QWidget):
    # Costanti per i range degli assi
    MOTOR_X_MIN, MOTOR_X_MAX = 0.0, 9.0
    MOTOR_Y_MIN, MOTOR_Y_MAX = 0.0, 6.0
    MOTOR_X_RANGE = MOTOR_X_MAX - MOTOR_X_MIN
    MOTOR_Y_RANGE = MOTOR_Y_MAX - MOTOR_Y_MIN
    
    FWAVE_X_MIN, FWAVE_X_MAX = 0.0, 10.0
    FWAVE_X_RANGE = FWAVE_X_MAX - FWAVE_X_MIN
    
    def __init__(self, plot_type="sensory", parent=None):
        super().__init__(parent)
        self.plot_type = plot_type
        self.points = []
        self.setMinimumHeight(350) 
        self.padding = 40 

    def set_data(self, points):
        self.points = points
        self.update() 

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        font = QFont("Arial", 9)
        painter.setFont(font)
        
        # Dimensioni area utile grafico
        w = self.width() - self.padding * 2
        h = self.height() - self.padding * 2
        
        # Origine assi (Basso-Sinistra)
        origin_x = self.padding
        origin_y = self.padding + h
        
        # 1. Sfondo Bianco Globale
        painter.setBrush(Qt.GlobalColor.white)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRect(0, 0, self.width(), self.height())
        
        # 2. Traslazione Origine
        # Ora (0,0) è l'angolo in basso a sinistra del grafico.
        # Y positivi vanno verso il BASSO (fuori grafico), Y negativi vanno verso l'ALTO.
        painter.translate(origin_x, origin_y) 
        
        # 3. Sfondo Grigio Area Grafico (Disegnato da 0 a -h)
        painter.setBrush(QColor("#FAFAFA"))
        painter.setPen(QPen(QColor(220, 220, 220), 1))
        painter.drawRect(0, -h, w, h)

        # 4. Disegno Sfondi Diagnostici
        if self.plot_type == "motor_cv" or self.plot_type == "sensory":
            self.draw_motor_cv_background(painter, w, h)
        elif self.plot_type == "motor_dml":
            self.draw_motor_dml_background(painter, w, h)
        elif self.plot_type == "fwave":
            self.draw_fwave_background(painter, w, h)

        # 5. Disegno Punti
        self.draw_points(painter, w, h)

    # --- COLORI DIAGNOSTICI ---
    def get_color_for_diagnosis(self, diag):
        if diag == "Axonal loss": return QColor(231, 76, 60, 220) # Rosso
        if diag == "Re/demyelinating (Definite)": return QColor(230, 126, 34, 220) # Arancio scuro
        if diag == "Re/demyelinating (Probable)": return QColor(241, 196, 15, 220) # Giallo/Arancio
        if diag == "Neuropathic": return QColor(52, 152, 219, 220) # Blu
        if diag == "Normal": return QColor(46, 204, 113, 220) # Verde
        return QColor(127, 140, 141, 220) # Grigio

    # --- FUNZIONI DI MAPPATURA ---
    def map_motor_x(self, sd_val, w):
        # SD da 0 a 8
        percent = (sd_val - self.MOTOR_X_MIN) / self.MOTOR_X_RANGE
        percent = max(0.0, min(1.0, percent))
        return w * percent
    
    def map_motor_y(self, sd_amp, h):
        # SD da 0 a 6 (Ampiezza persa)
        percent = (sd_amp - self.MOTOR_Y_MIN) / self.MOTOR_Y_RANGE
        percent = max(0.0, min(1.0, percent))
        return -h * percent # Y negativo verso l'alto
        
    def map_fwave_x(self, sd_fmin, w):
        # SD Latenza da 0 a 10
        sd_fmin = max(self.FWAVE_X_MIN, min(self.FWAVE_X_MAX, sd_fmin))
        return w * (sd_fmin - self.FWAVE_X_MIN) / self.FWAVE_X_RANGE

    def map_fwave_y(self, persist, lln, h):
        # Persistenza % (0-100). 100% = Alto (-h), 0% = Basso (0)
        # Input persist: 0-100
        clamped_persist = max(0.0, min(100.0, persist))
        # Y deve essere negativo per andare in alto
        return -(h * (clamped_persist / 100.0))

    # --- DISEGNO SFONDI ---

    def draw_motor_cv_background(self, painter, w, h):
        """ESTEEM Fig 1B: CV (X) vs Amp (Y)"""
        x_2_0 = self.map_motor_x(2.0, w)
        x_2_5 = self.map_motor_x(2.5, w)
        x_4_5 = self.map_motor_x(4.5, w)
        x_5_5 = self.map_motor_x(5.5, w)
        x_zero = self.map_motor_x(0.0, w)
        
        y_2_0 = self.map_motor_y(2.0, h)
        y_2_5 = self.map_motor_y(2.5, h)
        y_zero = self.map_motor_y(0.0, h)

        painter.save()
        painter.setOpacity(0.1)
        
        # Normal (Top-Left)
        painter.setBrush(self.get_color_for_diagnosis("Normal"))
        painter.drawRect(int(x_zero), int(y_2_0), int(x_2_0 - x_zero), int(y_zero - y_2_0))
        
        # Axonal (Bottom-Left)
        painter.setBrush(self.get_color_for_diagnosis("Axonal loss"))
        painter.drawRect(int(x_zero), -h, int(x_2_5 - x_zero), int(h + y_2_5))
        
        # Neuropathic (Middle)
        painter.setBrush(self.get_color_for_diagnosis("Neuropathic"))
        painter.drawRect(int(x_2_5), -h, int(x_4_5 - x_2_5), int(h))
        painter.drawRect(int(x_2_0), int(y_zero), int(x_2_5 - x_2_0), int(y_2_5 - y_zero))
        painter.drawRect(int(x_zero), int(y_2_5), int(x_2_0 - x_zero), int(y_2_0 - y_2_5))
        
        # Probable (Right-Mid)
        painter.setBrush(self.get_color_for_diagnosis("Re/demyelinating (Probable)"))
        painter.drawRect(int(x_4_5), -h, int(x_5_5 - x_4_5), int(h))
        
        # Definite (Right)
        painter.setBrush(self.get_color_for_diagnosis("Re/demyelinating (Definite)"))
        painter.drawRect(int(x_5_5), -h, int(w - x_5_5), int(h))
        
        painter.restore()
        self._draw_grid_and_labels_motor(painter, w, h, x_2_0, x_2_5, x_4_5, x_5_5, y_2_0, y_2_5, x_zero, y_zero, "CV")

    def draw_motor_dml_background(self, painter, w, h):
        """ESTEEM Fig 1A: DML (X) vs Amp (Y)"""
        x_2_0 = self.map_motor_x(2.0, w)
        x_2_5 = self.map_motor_x(2.5, w)
        x_6_0 = self.map_motor_x(6.0, w)
        x_8_0 = self.map_motor_x(8.0, w)
        x_zero = self.map_motor_x(0.0, w)
        
        y_2_0 = self.map_motor_y(2.0, h)
        y_2_5 = self.map_motor_y(2.5, h)
        y_zero = self.map_motor_y(0.0, h)

        painter.save()
        painter.setOpacity(0.1)
        
        # Normal
        painter.setBrush(self.get_color_for_diagnosis("Normal"))
        painter.drawRect(int(x_zero), int(y_2_0), int(x_2_0 - x_zero), int(y_zero - y_2_0))
        
        # Axonal
        painter.setBrush(self.get_color_for_diagnosis("Axonal loss"))
        painter.drawRect(int(x_zero), -h, int(x_2_5 - x_zero), int(h + y_2_5))
        
        # Neuropathic
        painter.setBrush(self.get_color_for_diagnosis("Neuropathic"))
        painter.drawRect(int(x_2_5), -h, int(x_6_0 - x_2_5), int(h))
        painter.drawRect(int(x_2_0), int(y_zero), int(x_2_5 - x_2_0), int(y_2_5 - y_zero))
        painter.drawRect(int(x_zero), int(y_2_5), int(x_2_0 - x_zero), int(y_2_0 - y_2_5))
        
        # Probable
        painter.setBrush(self.get_color_for_diagnosis("Re/demyelinating (Probable)"))
        painter.drawRect(int(x_6_0), -h, int(x_8_0 - x_6_0), int(h))
        
        # Definite
        painter.setBrush(self.get_color_for_diagnosis("Re/demyelinating (Definite)"))
        painter.drawRect(int(x_8_0), -h, int(w - x_8_0), int(h))
        
        painter.restore()
        self._draw_grid_and_labels_motor(painter, w, h, x_2_0, x_2_5, x_6_0, x_8_0, y_2_0, y_2_5, x_zero, y_zero, "DML")

    def draw_fwave_background(self, painter, w, h):
        """
        ESTEEM Fig 1D: F-Min Latency (X) vs Persistence (Y).
        FIX Y-AXIS: 100% in Alto (-h), 0% in Basso (0).
        """
        # Recupera LLN
        lln_val = self.points[0]['lln'] if self.points and self.points[0]['lln'] is not None else 20.0
        
        # Coordinate Y: map_fwave_y restituisce valori negativi (verso l'alto)
        y_top_screen = -h               # 100% Persistence
        y_lln_screen = self.map_fwave_y(lln_val, 0, h) # LLN line (es. -60)
        y_bottom_screen = 0             # 0% Persistence
        
        # Coordinate X (SD)
        normal_x = self.map_fwave_x(2.0, w)
        probable_x = self.map_fwave_x(7.0, w)
        definite_x = self.map_fwave_x(8.0, w)
        
        painter.save()
        painter.setOpacity(0.1)

        # 1. Definite Demyelinating (Colonna destra piena)
        painter.setBrush(self.get_color_for_diagnosis("Re/demyelinating (Definite)"))
        painter.drawRect(int(definite_x), int(y_top_screen), int(w - definite_x), int(h))

        # 2. Probable Demyelinating (Colonna centro-destra piena)
        painter.setBrush(self.get_color_for_diagnosis("Re/demyelinating (Probable)"))
        painter.drawRect(int(probable_x), int(y_top_screen), int(definite_x - probable_x), int(h))

        # 3. Neuropathic (Colonna centro-sinistra piena)
        # Latency 2-7 SD è Neuropathic (indipendentemente da persistence)
        painter.setBrush(self.get_color_for_diagnosis("Neuropathic"))
        painter.drawRect(int(normal_x), int(y_top_screen), int(probable_x - normal_x), int(h))

        # 4. Neuropathic (Basso-Sinistra)
        # Latency < 2 SD MA Persistence < LLN.
        # Disegniamo dalla linea LLN in giù fino a 0.
        height_neuro = y_bottom_screen - y_lln_screen # Poiché y_lln è negativo, questo è positivo (es. 0 - (-60) = 60)
        painter.drawRect(0, int(y_lln_screen), int(normal_x), int(height_neuro))

        # 5. Normal (Alto-Sinistra)
        # Latency < 2 SD E Persistence > LLN.
        # Disegniamo dalla cima (-h) in giù fino a LLN.
        height_normal = y_lln_screen - y_top_screen # (es. -60 - (-300) = 240)
        painter.setBrush(self.get_color_for_diagnosis("Normal"))
        painter.drawRect(0, int(y_top_screen), int(normal_x), int(height_normal))
        
        painter.restore()

        # --- GRIGLIA F-WAVE ---
        pen_dash = QPen(QColor(0,0,0,50), 1, Qt.PenStyle.DashLine)
        painter.setPen(pen_dash)
        
        # Linea LLN
        painter.drawLine(QPointF(0, y_lln_screen), QPointF(probable_x, y_lln_screen))
        
        # Linee Verticali SD
        painter.drawLine(QPointF(normal_x, -h), QPointF(normal_x, 0))
        painter.drawLine(QPointF(probable_x, -h), QPointF(probable_x, 0))
        painter.drawLine(QPointF(definite_x, -h), QPointF(definite_x, 0))
        
        # Assi
        pen_solid = QPen(QColor(0,0,0,100), 1, Qt.PenStyle.SolidLine)
        painter.setPen(pen_solid)
        painter.drawLine(0, 0, w, 0) # X Axis (0 Persistence)
        painter.drawLine(0, 0, 0, -h) # Y Axis (0 SD Latency)
        
        # Testi
        painter.setPen(QColor(0, 0, 0))
        font = QFont("Arial", 10, QFont.Weight.Bold)
        painter.setFont(font)
        fm = QFontMetrics(font)
        
        fmin_title = "Increase in F-min Latency (SD)"
        painter.drawText(int(w/2 - fm.horizontalAdvance(fmin_title)/2), 35, fmin_title)
        
        painter.save()
        painter.rotate(-90)
        persist_title = "F-wave Persistence (%)"
        painter.drawText(int(h/2 - fm.horizontalAdvance(persist_title)/2), -25, persist_title)
        painter.restore()
        
        # Etichette valori
        font.setPointSize(9)
        font.setBold(False)
        painter.setFont(font)
        painter.drawText(QPointF(normal_x-10, 15), "+2.0")
        painter.drawText(QPointF(probable_x-10, 15), "+7.0")
        painter.drawText(QPointF(definite_x-10, 15), "+8.0")
        
        painter.drawText(QPointF(5, y_lln_screen - 4), f"LLN ({int(lln_val)}%)")
        painter.drawText(QPointF(5, -h + 12), "100%")
        painter.drawText(QPointF(5, -4), "0%")

    def _draw_grid_and_labels_motor(self, painter, w, h, x1, x2, x3, x4, y1, y2, x0, y0, type_label):
        """Helper per griglie Motorie"""
        pen_dash = QPen(QColor(0,0,0,50), 1, Qt.PenStyle.DashLine)
        painter.setPen(pen_dash)
        
        painter.drawLine(QPointF(x1, 0), QPointF(x1, -h))
        painter.drawLine(QPointF(x2, 0), QPointF(x2, -h))
        painter.drawLine(QPointF(x3, 0), QPointF(x3, -h))
        painter.drawLine(QPointF(x4, 0), QPointF(x4, -h))
        painter.drawLine(QPointF(0, y1), QPointF(w, y1))
        painter.drawLine(QPointF(0, y2), QPointF(w, y2))
        
        pen_solid = QPen(QColor(0,0,0,100), 1, Qt.PenStyle.SolidLine)
        painter.setPen(pen_solid)
        painter.drawLine(0, int(y0), w, int(y0))
        painter.drawLine(int(x0), 0, int(x0), -h)

        painter.setPen(QColor(0, 0, 0))
        title_font = QFont("Arial", 10, QFont.Weight.Bold)
        painter.setFont(title_font)
        fm = QFontMetrics(title_font)
        
        x_title = "Decrease in Motor CV (SD)" if type_label == "CV" else "Increase in Motor DML (SD)"
        painter.drawText(int(w/2 - fm.horizontalAdvance(x_title)/2), 35, x_title)
        
        painter.save()
        painter.rotate(-90)
        y_title = "Decrease in Amp (SD)"
        painter.drawText(int(h/2 - fm.horizontalAdvance(y_title)/2), -25, y_title)
        painter.restore()
        
        num_font = QFont("Arial", 9)
        painter.setFont(num_font)
        labels_x = ["-2.0", "-2.5", "-4.5", "-5.5"] if type_label == "CV" else ["+2.0", "+2.5", "+6.0", "+8.0"]
        coords_x = [x1, x2, x3, x4]
        for coord, label in zip(coords_x, labels_x):
            painter.drawText(QPointF(coord - 10, 15), label)
        painter.drawText(QPointF(x0 + 5, y1 + 4), "-2.0")
        painter.drawText(QPointF(x0 + 5, y2 + 4), "-2.5")

    def draw_points(self, painter, w, h):
        fm = QFontMetrics(painter.font())
        drawn_pixel_positions = {}
        
        for point_data in self.points:
            x, y = 0, 0
            is_null = False
            diag_key = 'diagnosis' 

            try:
                sd_amp_pos = None
                if self.plot_type in ["sensory", "motor_cv", "motor_dml"]:
                    if point_data.get('sd_amp') is not None:
                         sd_amp_pos = -point_data['sd_amp'] # Negativo per Y (basso valore = alto Y grafico)

                if self.plot_type == "sensory":
                    if point_data['sd_cv'] is None or sd_amp_pos is None: continue 
                    is_null = point_data.get('cv_null', False)
                    x = self.map_motor_x(-point_data['sd_cv'], w) 
                    y = self.map_motor_y(sd_amp_pos, h) 
                
                elif self.plot_type == "motor_cv":
                    if point_data['sd_cv'] is None or sd_amp_pos is None: continue
                    is_null = point_data.get('cv_null', False)
                    x = self.map_motor_x(-point_data['sd_cv'], w) 
                    y = self.map_motor_y(sd_amp_pos, h) 
                    diag_key = 'diag_cv' 
                    
                elif self.plot_type == "motor_dml":
                    if point_data['sd_dml'] is None or sd_amp_pos is None: continue
                    is_null = point_data.get('dml_null', False)
                    x = self.map_motor_x(point_data['sd_dml'], w)
                    y = self.map_motor_y(sd_amp_pos, h) 
                    diag_key = 'diag_dml' 
                    
                elif self.plot_type == "fwave":
                    if point_data['sd_fmin'] is None or point_data['persist'] is None: continue 
                    x = self.map_fwave_x(point_data['sd_fmin'], w)
                    # Y negativo (verso l'alto)
                    y = self.map_fwave_y(point_data['persist'], point_data['lln'], h)
                
            except (TypeError, KeyError) as e:
                print(f"Errore disegno punto: {e} - Dati: {point_data}")
                continue 

            # Jitter anti-sovrapposizione
            pixel_key = (int(x), int(y))
            collision_count = drawn_pixel_positions.get(pixel_key, 0)
            if collision_count > 0:
                x_offset = (collision_count % 3) * 10 - 10 
                y_offset = (collision_count // 3) * 10 - 10 
                x += x_offset
                y += y_offset
            drawn_pixel_positions[pixel_key] = collision_count + 1

            diagnosis = point_data.get(diag_key, "Analysis Error")
            if diagnosis == "Missing data":
                color = QColor(127, 140, 141, 220) 
            else:
                color = self.get_color_for_diagnosis(diagnosis)
            
            painter.setPen(QPen(color, 2))
            painter.setBrush(QBrush(QColor(255, 255, 255, 200)))
            
            if is_null:
                painter.setPen(QPen(color, 2, Qt.PenStyle.SolidLine))
                painter.drawLine(int(x - 4), int(y - 4), int(x + 4), int(y + 4))
                painter.drawLine(int(x - 4), int(y + 4), int(x + 4), int(y - 4))
            else:
                painter.drawEllipse(QPointF(x, y), 6, 6)
            
            text = point_data['nerve']
            if is_null:
                null_type = "CV"
                if self.plot_type == "motor_dml": null_type = "DML"
                text += f" ({null_type} Null)"
            
            text_width = fm.horizontalAdvance(text)
            text_height = fm.height()
            rect_x = x + 10
            rect_y = y - (text_height / 2) - 2
            
            # Evita testo fuori bordo destro
            if rect_x + text_width + 8 > w:
                rect_x = x - text_width - 18
            
            painter.setBrush(QColor(255, 255, 255, 180))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(int(rect_x), int(rect_y), int(text_width + 8), int(text_height + 4), 3, 3)
            
            painter.setPen(Qt.GlobalColor.black)
            painter.drawText(QPointF(rect_x + 4, y + 4), text)


class AnalysisPlotDialog(QDialog):
    def __init__(self, results_data, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Analysis Results Visualization")
        self.setMinimumSize(850, 750)
        
        # Rendiamo la finestra NON modale (permette di cliccare sulla finestra principale)
        self.setWindowModality(Qt.WindowModality.NonModal) 

        layout = QVBoxLayout(self)
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)
        
        # Legend static widget (non cambia con i dati)
        self.legend_widget = self._create_legend_widget()
        
        # Button Box
        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        self.save_figure_button = self.button_box.addButton("Save Combined Figure", QDialogButtonBox.ButtonRole.ActionRole)
        self.print_figure_button = self.button_box.addButton("Print Combined Figure", QDialogButtonBox.ButtonRole.ActionRole)
        self.save_figure_button.clicked.connect(self.save_combined_figure)
        self.print_figure_button.clicked.connect(self.print_combined_figure)
        self.button_box.rejected.connect(self.close) # Close chiude solo la finestra
        
        layout.addWidget(self.legend_widget)
        layout.addWidget(self.button_box)
        
        # Inizializza i dati
        self.update_data(results_data)

    def update_data(self, results_data):
        """
        Metodo pubblico per aggiornare i grafici in tempo reale
        senza chiudere la finestra.
        """
        self.results = results_data
        
        # Salva l'indice della tab corrente per ripristinarlo dopo il refresh
        current_idx = self.tabs.currentIndex()
        
        # Rimuove tutte le tab esistenti
        self.tabs.clear()
        
        # Ricrea le tab con i nuovi dati
        self.tabs.addTab(self.create_plot_tab("motor_cv"), "Motor CV vs Amp")
        self.tabs.addTab(self.create_plot_tab("motor_dml"), "Motor DML vs Amp")
        self.tabs.addTab(self.create_plot_tab("sensory"), "Sensory Nerves")
        self.tabs.addTab(self.create_plot_tab("fwave"), "F-Wave Nerves")
        
        # Ripristina la tab che l'utente stava guardando
        if current_idx >= 0:
            self.tabs.setCurrentIndex(current_idx)
        
    def create_plot_tab(self, plot_type):
        container = QWidget()
        layout = QVBoxLayout(container)
        
        plottable_points = []
        errors_list = []
        missing_list = []
            
        if plot_type == "sensory":
            plotter = PlotterWidget("sensory")
            for nerve in self.results["sensory"]:
                if nerve['diagnosis'] == "Analysis Error":
                    errors_list.append(nerve)
                elif nerve['diagnosis'] == "Missing data":
                    missing_list.append(nerve)
                elif nerve['sd_amp'] is not None and nerve['sd_cv'] is not None:
                    plottable_points.append(nerve)
            
        elif plot_type == "fwave":
            plotter = PlotterWidget("fwave")
            for nerve in self.results["fwave"]:
                if nerve['diagnosis'] == "Analysis Error":
                    errors_list.append(nerve)
                elif nerve['diagnosis'] == "Missing data":
                    missing_list.append(nerve)
                elif nerve['sd_fmin'] is not None and nerve['persist'] is not None:
                    plottable_points.append(nerve)
        
        elif plot_type == "motor_cv":
            plotter = PlotterWidget("motor_cv")
            for nerve in self.results["motor"]:
                if "Analysis Error" in nerve['diagnosis']: errors_list.append(nerve)
                elif "Missing data" in nerve['diagnosis']: missing_list.append(nerve)
                elif nerve['sd_cv'] is not None and nerve['sd_amp'] is not None:
                    plottable_points.append(nerve)

        elif plot_type == "motor_dml":
            plotter = PlotterWidget("motor_dml")
            for nerve in self.results["motor"]:
                if "Analysis Error" in nerve['diagnosis']: errors_list.append(nerve)
                elif "Missing data" in nerve['diagnosis']: missing_list.append(nerve)
                elif nerve['sd_dml'] is not None and nerve['sd_amp'] is not None:
                    plottable_points.append(nerve)
        
        plotter.set_data(plottable_points)
        layout.addWidget(plotter)
        
        if errors_list or missing_list:
            layout.addWidget(self._create_info_box(errors_list, missing_list))
            
        return container

    def _create_info_box(self, errors_list, missing_list):
        group = QGroupBox("Nerves Not Plotted")
        group_layout = QVBoxLayout()
        list_widget = QListWidget()
        list_widget.setMaximumHeight(100)
        if errors_list:
            item_header = QListWidgetItem("--- Analysis Errors ---")
            item_header.setForeground(QColor("red"))
            list_widget.addItem(item_header)
            for nerve in errors_list:
                item = QListWidgetItem(f"{nerve['nerve']}  ->  {nerve['diagnosis']}")
                item.setForeground(QColor("red"))
                list_widget.addItem(item)
        if missing_list:
            item_header = QListWidgetItem("--- Missing Data ---")
            item_header.setForeground(QColor(231, 76, 60))
            list_widget.addItem(item_header)
            for nerve in missing_list:
                item = QListWidgetItem(f"{nerve['nerve']}  ->  {nerve['diagnosis']}")
                item.setForeground(QColor(231, 76, 60))
                list_widget.addItem(item)
        group_layout.addWidget(list_widget)
        group.setLayout(group_layout)
        return group
        
    def _points_for_plot(self, plot_type):
        """Return plottable points for a plot type without creating a visible tab."""
        if not isinstance(self.results, dict):
            return []
        plottable_points = []
        if plot_type == "sensory":
            for nerve in self.results.get("sensory", []):
                if nerve.get('diagnosis') not in ("Analysis Error", "Missing data") and nerve.get('sd_amp') is not None and nerve.get('sd_cv') is not None:
                    plottable_points.append(nerve)
        elif plot_type == "fwave":
            for nerve in self.results.get("fwave", []):
                if nerve.get('diagnosis') not in ("Analysis Error", "Missing data") and nerve.get('sd_fmin') is not None and nerve.get('persist') is not None:
                    plottable_points.append(nerve)
        elif plot_type == "motor_cv":
            for nerve in self.results.get("motor", []):
                diagnosis = nerve.get('diagnosis', '')
                if "Analysis Error" not in diagnosis and "Missing data" not in diagnosis and nerve.get('sd_cv') is not None and nerve.get('sd_amp') is not None:
                    plottable_points.append(nerve)
        elif plot_type == "motor_dml":
            for nerve in self.results.get("motor", []):
                diagnosis = nerve.get('diagnosis', '')
                if "Analysis Error" not in diagnosis and "Missing data" not in diagnosis and nerve.get('sd_dml') is not None and nerve.get('sd_amp') is not None:
                    plottable_points.append(nerve)
        return plottable_points

    def render_combined_figure(self, width=1800, height=1300):
        """Render all diagnostic plots into one printable QImage."""
        image = QImage(width, height, QImage.Format.Format_ARGB32)
        image.fill(Qt.GlobalColor.white)
        painter = QPainter(image)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        try:
            margin = 42
            title_h = 44
            gap = 34
            legend_h = 70
            cell_w = int((width - 2 * margin - gap) / 2)
            cell_h = int((height - 2 * margin - gap - legend_h) / 2)
            plot_h = cell_h - title_h
            plot_types = [
                ("motor_cv", "Motor CV vs CMAP amplitude"),
                ("motor_dml", "Motor DML vs CMAP amplitude"),
                ("sensory", "Sensory CV vs SNAP amplitude"),
                ("fwave", "F-wave latency vs persistence"),
            ]
            title_font = QFont("Arial", 18)
            title_font.setBold(True)
            sub_font = QFont("Arial", 12)

            painter.setPen(Qt.GlobalColor.black)
            painter.setFont(title_font)
            painter.drawText(margin, 30, "NeuroScan diagnostic plots")
            painter.setFont(sub_font)
            painter.setPen(QColor(90, 90, 90))
            painter.drawText(margin, 56, "Combined figure generated from the active analysis results")

            top = margin + 44
            for idx, (plot_type, title) in enumerate(plot_types):
                row = idx // 2
                col = idx % 2
                x = margin + col * (cell_w + gap)
                y = top + row * (cell_h + gap)
                painter.setPen(QColor(40, 40, 40))
                painter.setFont(sub_font)
                painter.drawText(x, y + 20, title)

                plotter = PlotterWidget(plot_type)
                plotter.resize(cell_w, plot_h)
                plotter.set_data(self._points_for_plot(plot_type))
                sub_img = QImage(cell_w, plot_h, QImage.Format.Format_ARGB32)
                sub_img.fill(Qt.GlobalColor.white)
                sub_painter = QPainter(sub_img)
                try:
                    plotter.render(sub_painter)
                finally:
                    sub_painter.end()
                painter.drawImage(x, y + title_h, sub_img)

            # Compact legend at the bottom.
            legend_y = height - margin - legend_h + 18
            painter.setFont(sub_font)
            painter.setPen(Qt.GlobalColor.black)
            painter.drawText(margin, legend_y, "Legend:")
            plotter = PlotterWidget()
            diagnoses = ["Normal", "Neuropathic", "Axonal loss", "Re/demyelinating (Probable)", "Re/demyelinating (Definite)"]
            x = margin + 70
            for diag in diagnoses:
                color = plotter.get_color_for_diagnosis(diag)
                painter.setBrush(QBrush(color))
                painter.setPen(QPen(color.darker(110), 1))
                painter.drawRoundedRect(x, legend_y - 14, 18, 18, 3, 3)
                painter.setPen(Qt.GlobalColor.black)
                painter.drawText(x + 26, legend_y, diag)
                x += 26 + painter.fontMetrics().horizontalAdvance(diag) + 28
        finally:
            painter.end()
        return image

    def combined_figure_png_bytes(self):
        """Return the combined plot figure as PNG bytes for HTML embedding."""
        image = self.render_combined_figure()
        buffer = io.BytesIO()
        # QImage.save expects a QIODevice or a filename. Use QBuffer for Qt-safe bytes.
        from PyQt6.QtCore import QBuffer, QByteArray, QIODevice
        byte_array = QByteArray()
        qbuffer = QBuffer(byte_array)
        qbuffer.open(QIODevice.OpenModeFlag.WriteOnly)
        image.save(qbuffer, "PNG")
        qbuffer.close()
        return bytes(byte_array)

    def save_combined_figure(self):
        path, _ = QFileDialog.getSaveFileName(self, "Save Combined NeuroScan Figure", "neuroscan_combined_plots.png", "PNG Image (*.png)")
        if not path:
            return
        if not path.lower().endswith(".png"):
            path += ".png"
        image = self.render_combined_figure()
        if image.save(path, "PNG"):
            QMessageBox.information(self, "Combined Figure", f"Figure saved to:\n{path}")
        else:
            QMessageBox.warning(self, "Combined Figure", "Could not save the figure.")

    def print_combined_figure(self):
        try:
            from PyQt6.QtPrintSupport import QPrinter, QPrintDialog
        except Exception as exc:
            QMessageBox.warning(self, "Print Figure", f"Qt print support is not available:\n{exc}")
            return
        printer = QPrinter(QPrinter.PrinterMode.HighResolution)
        dialog = QPrintDialog(printer, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        image = self.render_combined_figure()
        painter = QPainter(printer)
        try:
            page_rect = printer.pageRect(QPrinter.Unit.DevicePixel)
            scaled = image.scaled(page_rect.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            x = page_rect.x() + (page_rect.width() - scaled.width()) // 2
            y = page_rect.y() + (page_rect.height() - scaled.height()) // 2
            painter.drawImage(x, y, scaled)
        finally:
            painter.end()

    def _create_legend_widget(self):
        legend_box = QGroupBox("Legend (Color Codex)")
        layout = QHBoxLayout()
        plotter = PlotterWidget() 
        diagnoses = ["Normal", "Neuropathic", "Axonal loss", "Re/demyelinating (Probable)", "Re/demyelinating (Definite)"]
        for diag in diagnoses:
            label_text = diag  # <--- FIX: Mantiene il testo completo
            color = plotter.get_color_for_diagnosis(diag)
            item_layout = QHBoxLayout()
            item_layout.addWidget(ColorSwatch(color))
            item_layout.addWidget(QLabel(label_text))
            layout.addLayout(item_layout)
            layout.addStretch(1)
        legend_box.setLayout(layout)
        legend_box.setMaximumHeight(80)
        return legend_box


class CustomDoubleSpinBox(QDoubleSpinBox):
    # ... (invariato) ...
    def textFromValue(self, value: float) -> str:
        if value == int(value):
            return f"{value:.1f}"
        return f"{value:.3f}".rstrip('0')


class SettingsDialog(QDialog):
    # ... (invariato) ...
    def __init__(self, current_settings, all_settings, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Reference Values ​​Settings")
        self.setMinimumWidth(500)
        
        self.native_defaults = parent.DEFAULT_SETTINGS
        self.all_settings = all_settings
        self.current_settings = current_settings
        
        self.editors = {}
        self.us_locale = QLocale(QLocale.Language.English, QLocale.Country.UnitedStates)
        
        layout = QVBoxLayout(self)

        info = QLabel(
            "Native Defaults use the built-in nerve-specific reference database. "
            "Custom presets override modality-level mean/SD values and are recorded in the audit trail."
        )
        info.setWordWrap(True)
        info.setStyleSheet("color:#6E6E73; font-size:11px;")
        layout.addWidget(info)
        
        preset_layout = QHBoxLayout()
        preset_layout.addWidget(QLabel("Load Preset:"))
        self.preset_combo = QComboBox()
        self.preset_combo.addItems(list(self.all_settings.keys()))
        
        current_preset_name = self.find_preset_name(current_settings)
        self.preset_combo.setCurrentText(current_preset_name)
        
        self.preset_combo.currentTextChanged.connect(self.load_preset_to_editors)
        preset_layout.addWidget(self.preset_combo)
        
        self.restore_button = QPushButton("Restore Native Defaults")
        self.restore_button.setObjectName("secondary")
        self.restore_button.clicked.connect(self.restore_native_defaults)
        preset_layout.addWidget(self.restore_button)
        
        layout.addLayout(preset_layout)
        
        form_layout = QFormLayout()
        for table, params in current_settings.items():
            group_box = QGroupBox(f"{table.replace('_', ' ').title()} Settings")
            group_layout = QFormLayout()
            self.editors[table] = {}
            for key, value in params.items():
                label = QLabel(f"{key.replace('_', ' ').title()}:")
                editor = CustomDoubleSpinBox()
                editor.setLocale(self.us_locale)
                editor.setDecimals(3)
                if key.endswith("_sd"):
                    editor.setRange(0.001, 1000)
                else:
                    editor.setRange(0, 1000)
                editor.setValue(value)
                group_layout.addRow(label, editor)
                self.editors[table][key] = editor
            group_box.setLayout(group_layout)
            form_layout.addRow(group_box)
        layout.addLayout(form_layout)
        
        button_layout = QHBoxLayout()
        
        self.save_button = QPushButton("Save (Session)")
        self.save_button.clicked.connect(self.accept)
        
        self.save_as_button = QPushButton("Save As Preset...")
        self.save_as_button.clicked.connect(self.save_as_preset)
        
        self.save_default_button = QPushButton("Save as Default")
        self.save_default_button.clicked.connect(self.save_as_default)
        
        button_layout.addWidget(self.save_button)
        button_layout.addWidget(self.save_as_button)
        button_layout.addWidget(self.save_default_button)
        
        layout.addLayout(button_layout)
        
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        button_box.button(QDialogButtonBox.StandardButton.Ok).setText("Close")
        button_box.accepted.connect(self.accept)
        layout.addWidget(button_box)

    def find_preset_name(self, settings_to_find):
        for name, preset in self.all_settings.items():
            if preset == settings_to_find:
                return name
        return "Native Defaults"

    def load_preset_to_editors(self, preset_name):
        if preset_name not in self.all_settings:
            return
        settings_to_load = self.all_settings[preset_name]
        for table, params in settings_to_load.items():
            for key, value in params.items():
                if table in self.editors and key in self.editors[table]:
                    self.editors[table][key].setValue(value)

    def restore_native_defaults(self):
        # 1. Carica i valori nei campi
        self.load_preset_to_editors("Native Defaults")
        # 2. Imposta il menu a tendina su Native Defaults
        self.preset_combo.setCurrentText("Native Defaults")
        
        # 3. Salva su file forzando il nuovo default
        self.parent().save_settings_to_file(self.all_settings, new_default="Native Defaults")
        
        QMessageBox.information(self, "Restored", "Native defaults restored and set as startup default.")

    def get_current_values(self):
        new_settings = {}
        for table, params in self.editors.items():
            new_settings[table] = {}
            for key, editor in params.items():
                new_settings[table][key] = editor.value()
        return new_settings

    def save_as_preset(self):
        current_values = self.get_current_values()
        preset_name, ok = QInputDialog.getText(self, "Save Preset", "Enter a name for this preset:")
        if ok and preset_name:
            if preset_name == "Native Defaults" or preset_name == "__default__":
                QMessageBox.warning(self, "Invalid Name", "This name is reserved. Please choose another.")
                return
            self.all_settings[preset_name] = current_values
            if self.preset_combo.findText(preset_name) == -1:
                self.preset_combo.addItem(preset_name)
            self.preset_combo.setCurrentText(preset_name)
            QMessageBox.information(self, "Preset Saved", f"Preset '{preset_name}' saved.")
            self.parent().save_settings_to_file(self.all_settings)

    def save_as_default(self):
        current_values = self.get_current_values()
        preset_name = self.find_preset_name(current_values)
        
        if preset_name == "Native Defaults":
            preset_name, ok = QInputDialog.getText(self, "Save as Default", "First, save these settings as a new preset. Enter a name:")
            if not (ok and preset_name):
                return
            if preset_name == "Native Defaults" or preset_name == "__default__":
                QMessageBox.warning(self, "Invalid Name", "This name is reserved. Please choose another.")
                return
            
            # Aggiungi il nuovo preset alla lista (senza __default__)
            self.all_settings[preset_name] = current_values
            if self.preset_combo.findText(preset_name) == -1:
                self.preset_combo.addItem(preset_name)
            self.preset_combo.setCurrentText(preset_name)
        
        # --- MODIFICA QUI ---
        # NON aggiungere self.all_settings["__default__"] = preset_name
        # Invece, passa il nome del preset al metodo di salvataggio del genitore
        QMessageBox.information(self, "Default Saved", f"'{preset_name}' is now the default preset on startup.")
        self.parent().save_settings_to_file(self.all_settings, new_default=preset_name)
        # --------------------

    def get_session_settings(self):
        return self.get_current_values()


class MainWindow(QMainWindow):
    # ... (invariato) ...
    MANUAL_HEADERS = {
        "motor":   ["Nerve", "Amp", "CV", "DML [ms]"],
        "sensory": ["Nerve", "Amp", "CV", "DML [ms]"],
        "fwave":   ["Nerve", "Fmin", "F / M (%)"]
    }
    
    DEFAULT_SETTINGS = {
        "motor": {
            "amp": 6.0,       # Media conservativa (Tibiale ~10mV, Peroneo ~3mV) [cite: 1000]
            "cv": 52.0,       # Media ponderata (Braccia ~58, Gambe ~46) [cite: 1000]
            "dml": 3.8,       # Latenza distale media [cite: 1000]
            "amp_sd": 0.30,   # SD relativa (Coefficiente di variazione ~30%)
            "cv_sd": 0.10,    # SD relativa (CV ~10% della media)
            "dml_sd": 0.15    # SD relativa
        },
        "sensory": {
            "amp": 25.0,      # Media (Mediano/Ulnare ~30-40uV, Surale ~15uV) [cite: 979]
            "cv": 55.0,       # Media Sensitiva [cite: 979]
            "amp_sd": 0.35,   # Alta variabilità nelle ampiezze sensitive
            "cv_sd": 0.09     # ~9-10% variabilità velocità
        },
        "fwave": {
            "fmin": 28.0,     # Media F-Wave (molto variabile per altezza)
            "fmin_sd": 0.12,  
            "fwave_persist_lln": 20.0 # Cutoff persistenza normale (ESTEEM Fig 1D) [cite: 232]
        }
    }
    
    SETTINGS_FILE = "neuroscan_settings.json"

    def __init__(self):
        super().__init__()
        self.setWindowTitle("ELETTROMIOAPP")
        self.setGeometry(100, 100, 1100, 800)
        self.threadpool = QThreadPool()
        self.plot_dialog = None
        self.latest_results = { "motor": [], "sensory": [], "fwave": [] }
        self.all_settings = {}
        self.settings = {}
        self.pediatric_mode = False
        self.load_settings()
        self.init_ui()
        self.apply_styles()
    
    def apply_styles(self):
        # ... (invariato) ...
        self.setStyleSheet("""
            QWidget {
                background-color: #FFFFFF;
                font-family: -apple-system, "SF Pro Display", "Helvetica Neue", Arial;
                color: #282828;
            }
            QFrame#card {
                background-color: #FFFFFF;
                border-radius: 12px;
                padding: 12px;
                border: 1px solid rgba(0,0,0,0.08);
            }
            QLabel#appTitle {
                font-size: 22px;
                font-weight: 600;
                color: #282828;
            }
            QLabel#footer {
                color: #86868B;
                font-size: 12px;
                padding-top: 6px;
            }
            QPushButton {
                background-color: #007AFF;
                color: white;
                border: none;
                padding: 8px 14px;
                border-radius: 8px;
                font-size: 13px;
                min-height: 28px;
            }
            QPushButton:hover {
                background-color: #339CFF;
            }
            QPushButton:pressed {
                background-color: #0062CE;
            }
            QPushButton#secondary {
                background-color: transparent;
                color: #007AFF;
                border: 1px solid rgba(0,122,255,0.3);
            }
            QPushButton#secondary:hover {
                background-color: rgba(0,122,255,0.08);
                border: 1px solid rgba(0,122,255,0.5);
            }
            QTabWidget::pane { border: 0; }
            QTabBar::tab {
                background: transparent;
                padding: 8px 14px;
                margin-right: 4px;
                font-size: 13px;
                border-radius: 8px;
            }
            QTabBar::tab:hover {
                background: rgba(0,0,0,0.05);
            }
            QTabBar::tab:selected {
                background: rgba(0,122,255,0.15);
                color: #007AFF;
                font-weight: 600;
            }
            QTextEdit {
                background-color: #FAFAFA;
                border-radius: 10px;
                padding: 8px;
                border: 1px solid rgba(0,0,0,0.08);
                selection-background-color: #CDE5FF;
            }
            QGroupBox {
                font-weight: 600;
                font-size: 14px;
                color: #1C1C1E;
                border: 1px solid rgba(0,0,0,0.05);
                border-radius: 10px;
                margin-top: 18px;
                padding-top: 10px;
                padding-left: 8px;
                padding-right: 8px;
                padding-bottom: 8px;
                background-color: #FFFFFF;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 2px 6px;
                background-color: #FFFFFF;
                color: #007AFF;
                font-size: 14px;
            }
            QScrollBar:vertical {
                border: none;
                background: transparent;
                width: 8px;
                margin: 0px 0px 0px 0px;
            }
            QScrollBar::handle:vertical {
                background: rgba(0,0,0,0.25);
                border-radius: 4px;
                min-height: 24px;
            }
            QScrollBar::handle:vertical:hover {
                background: rgba(0,0,0,0.4);
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                background: none;
                height: 0px;
            }
            QScrollBar:horizontal {
                border: none;
                background: transparent;
                height: 8px;
                margin: 0px 0px 0px 0px;
            }
            QScrollBar::handle:horizontal {
                background: rgba(0,0,0,0.25);
                border-radius: 4px;
                min-width: 24px;
            }
            QScrollBar::handle:horizontal:hover {
                background: rgba(0,0,0,0.4);
            }
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
                background: none;
                width: 0px;
            }
            QCheckBox {
                spacing: 8px;
            }
            QCheckBox::indicator {
                width: 16px;
                height: 16px;
                border-radius: 5px;
                border: 1px solid #BDBDBD;
                background-color: #F8F8F8;
            }
            QCheckBox::indicator:hover {
                border: 1px solid #007AFF;
            }
            QCheckBox::indicator:checked {
                background-color: #007AFF;
                border: 1px solid #007AFF;
                image: url(data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIyNCIgaGVpZ2h0PSIyNCIgdmlld0JveD0iMCAwIDI0IDI0IiBmaWxsPSJub25lIiBzdHJva2U9IndoaXRlIiBzdHJva2Utd2lkdGg9IjMiIHN0cm9rZS1saW5lY2FwPSJyb3VuZCIgc3Ryb2tlLWxpbmVqb2luPSJyb3VuZCI+PHBvbHlsaW5lIHBvaW50cz0iMjAgNiA5IDE3IDQgMTIiPjwvcG9seWxpbmU+PC9zdmc+);
            }
        """)
    
    def init_ui(self):
        main_widget = QWidget()
        main_layout = QVBoxLayout(main_widget)
        main_layout.setContentsMargins(16, 8, 16, 8)
        main_layout.setSpacing(8)
        self.setCentralWidget(main_widget)
        
        # --- HEADER ---
        header = QHBoxLayout()
        title_label = QLabel("⚕️ NeuroScan")
        title_label.setObjectName("appTitle")
        title_font = QFont()
        title_font.setPointSize(22)
        title_font.setBold(True)
        title_label.setFont(title_font)
        header.addWidget(title_label, alignment=Qt.AlignmentFlag.AlignLeft)
        subtitle = QLabel("Nerve damage analyzer from electromyographic findings (ESTEEM Protocol)")
        subtitle.setStyleSheet("color: #6E6E73; font-size: 12px;")
        header.addWidget(subtitle, alignment=Qt.AlignmentFlag.AlignRight)
        main_layout.addLayout(header, stretch=1)
        
        central_container = QWidget()
        central_layout = QVBoxLayout(central_container)
        central_layout.setContentsMargins(0, 0, 0, 0)
        central_layout.setSpacing(10)
        
        card = QFrame()
        card.setObjectName("card")
        card_layout = QVBoxLayout(card)
        card_layout.setSpacing(10)
        
        # --- BARRA DEI CONTROLLI (RISTRTUTTURATA) ---
        controls_layout = QHBoxLayout()
        
        # 1. GRUPPO SINISTRA: Pulsanti Operativi (Settings, Load, Analyze)
        left_buttons_layout = QHBoxLayout()
        left_buttons_layout.setSpacing(10)
        
        self.settings_button = QPushButton("⚙️ Settings")
        self.settings_button.setObjectName("secondary")
        self.settings_button.clicked.connect(self.open_settings_dialog)
        self.settings_button.setToolTip("Configure Reference Values (Mean/SD)")
        
        self.load_button = QPushButton("📂 Select File")
        self.load_button.setStyleSheet("font-size: 14px; padding: 6px 14px; font-weight: bold;")
        self.load_button.clicked.connect(self.load_file)

        self.reanalyze_button = QPushButton("🔁 Re-analyze")
        self.reanalyze_button.setObjectName("secondary")
        self.reanalyze_button.clicked.connect(self.reanalyze_current_data)
        self.reanalyze_button.setToolTip("Refresh the diagnosis using the currently loaded data and the current reference settings")        

        self.show_graphs_button = QPushButton("📈 Show Graphs")
        self.show_graphs_button.setObjectName("secondary")
        self.show_graphs_button.clicked.connect(self.open_graphs_window)

        self.export_report_button = QPushButton("💾 Export Report")
        self.export_report_button.setObjectName("secondary")
        self.export_report_button.clicked.connect(self.export_report)
        self.export_report_button.setToolTip("Export a plain-text audit report with nerve-level evidence")

        self.export_html_report_button = QPushButton("🖨 Report + Graphs")
        self.export_html_report_button.setObjectName("secondary")
        self.export_html_report_button.clicked.connect(self.export_html_report_with_graphs)
        self.export_html_report_button.setToolTip("Export a printable HTML report with the combined diagnostic figure embedded")

        self.phase2_batch_button = QPushButton("🧩 Phase 2 Batch")
        self.phase2_batch_button.setObjectName("secondary")
        self.phase2_batch_button.clicked.connect(self.run_phase2_batch_builder)
        self.phase2_batch_button.setToolTip("Batch anonymize DOCX reports and build the validation dataset")
        
        left_buttons_layout.addWidget(self.settings_button)
        left_buttons_layout.addWidget(self.load_button)
        left_buttons_layout.addWidget(self.reanalyze_button)
        left_buttons_layout.addWidget(self.show_graphs_button)
        left_buttons_layout.addWidget(self.export_report_button)
        left_buttons_layout.addWidget(self.export_html_report_button)
        left_buttons_layout.addWidget(self.phase2_batch_button)
        
        # 2. SPACER CENTRALE
        controls_layout.addLayout(left_buttons_layout)
        controls_layout.addStretch(1)
        
        # 3. GRUPPO DESTRA: Input Paziente (Età, Altezza)
        right_inputs_layout = QHBoxLayout()
        right_inputs_layout.setSpacing(8)
        
        self.lbl_age = QLabel("Age:")
        self.lbl_age.setStyleSheet("font-weight: bold; color: #555;")
        self.age_spin = QDoubleSpinBox()
        self.age_spin.setRange(0, 110)
        self.age_spin.setDecimals(0)
        self.age_spin.setSuffix(" yrs")
        self.age_spin.setValue(40)
        self.age_spin.setFixedWidth(80)
        
        self.lbl_height = QLabel("Height:")
        self.lbl_height.setStyleSheet("font-weight: bold; color: #555;")
        self.height_spin = QDoubleSpinBox()
        self.height_spin.setRange(50, 250)
        self.height_spin.setDecimals(0)
        self.height_spin.setSuffix(" cm")
        self.height_spin.setValue(170)
        self.height_spin.setFixedWidth(90)
        self.age_spin.valueChanged.connect(self.run_analysis)
        self.height_spin.valueChanged.connect(self.run_analysis)
        
        right_inputs_layout.addWidget(self.lbl_age)
        right_inputs_layout.addWidget(self.age_spin)
        right_inputs_layout.addWidget(self.lbl_height)
        right_inputs_layout.addWidget(self.height_spin)

        # --- MODE TOGGLE BUTTON ---
        # A single checkable button that switches between Adult and Pediatric mode.
        # When unchecked → Adult (blue); when checked → Pediatric (red).
        right_inputs_layout.addSpacing(8)
        self.mode_toggle_btn = QPushButton("Switch to Pediatric Mode")
        self.mode_toggle_btn.setCheckable(True)
        self.mode_toggle_btn.setChecked(False)
        self.mode_toggle_btn.setToolTip(
            "Currently: Adult Mode\n"
            "Click to switch to Pediatric Mode (0–14 months)"
        )
        self.mode_toggle_btn.setStyleSheet("""
            QPushButton {
                background-color: #007AFF;
                color: white;
                border: none;
                border-radius: 14px;
                padding: 5px 14px;
                font-size: 12px;
                font-weight: 600;
                min-width: 130px;
            }
            QPushButton:hover  { background-color: #339CFF; }
            QPushButton:checked {
                background-color: #C0392B;
            }
            QPushButton:checked:hover { background-color: #E74C3C; }
        """)
        self.mode_toggle_btn.toggled.connect(self._on_pediatric_toggled)
        right_inputs_layout.addWidget(self.mode_toggle_btn)

        # Age-in-months spinbox (hidden by default, shown in pediatric mode)
        self.lbl_age_months = QLabel("Age:")
        self.lbl_age_months.setStyleSheet("font-weight: bold; color: #C0392B;")
        self.age_months_spin = QDoubleSpinBox()
        self.age_months_spin.setRange(0, 14)
        self.age_months_spin.setDecimals(0)
        self.age_months_spin.setSuffix(" mo")
        self.age_months_spin.setValue(6)
        self.age_months_spin.setFixedWidth(72)
        self.age_months_spin.valueChanged.connect(self.run_analysis)
        self.lbl_age_months.setVisible(False)
        self.age_months_spin.setVisible(False)
        right_inputs_layout.addWidget(self.lbl_age_months)
        right_inputs_layout.addWidget(self.age_months_spin)
        
        controls_layout.addLayout(right_inputs_layout)
        # ---------------------------------------------
        
        card_layout.addLayout(controls_layout)
        
        # --- SPLITTER ---
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(True)
        splitter.setHandleWidth(6)
        splitter.setStretchFactor(0, 7)
        splitter.setStretchFactor(1, 3)
        
        left_container = QWidget()
        left_layout = QVBoxLayout(left_container)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(8)
        
        self.tabs = QTabWidget()
        self.file_tab, self.manual_tab = QWidget(), QWidget()
        self.tabs.addTab(self.file_tab, "Upload from File (.doc/.docx)")
        self.tabs.addTab(self.manual_tab, "Manual Data Entry")
        self.setup_file_tab()
        self.setup_manual_tab()
        
        left_layout.addWidget(self.tabs)
        left_scroll = QScrollArea()
        left_scroll.setWidgetResizable(True)
        left_scroll.setWidget(left_container)
        
        right_container = QWidget()
        right_layout = QVBoxLayout(right_container)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(10)
        
        summary_card = QFrame()
        summary_card.setObjectName("card")
        summary_layout = QVBoxLayout(summary_card)
        summary_label = QLabel("Diagnosis Summary")
        summary_label.setStyleSheet("font-weight: 700; font-size: 14px;")
        summary_layout.addWidget(summary_label)
        self.summary_output = QTextEdit()
        self.summary_output.setReadOnly(True)
        self.summary_output.setPlaceholderText("Analysis results based on ESTEEM criteria will appear here...")
        summary_layout.addWidget(self.summary_output)
        right_layout.addWidget(summary_card)

        # --- VALIDATION PANEL ---
        self.validation_card = QFrame()
        self.validation_card.setObjectName("card")
        validation_layout = QVBoxLayout(self.validation_card)
        validation_label = QLabel("Exam Validation")
        validation_label.setStyleSheet("font-weight: 700; font-size: 14px;")
        validation_layout.addWidget(validation_label)
        self.validation_output = QLabel("Load data to validate exam completeness.")
        self.validation_output.setWordWrap(True)
        self.validation_output.setStyleSheet("font-size: 12px; color: #555;")
        validation_layout.addWidget(self.validation_output)
        right_layout.addWidget(self.validation_card)

        evidence_card = QFrame()
        evidence_card.setObjectName("card")
        evidence_layout = QVBoxLayout(evidence_card)
        evidence_label = QLabel("Evidence / Audit Trail")
        evidence_label.setStyleSheet("font-weight: 700; font-size: 14px;")
        evidence_layout.addWidget(evidence_label)
        self.evidence_output = QTextEdit()
        self.evidence_output.setReadOnly(True)
        self.evidence_output.setMaximumHeight(180)
        self.evidence_output.setPlaceholderText("Observed values, z-scores and rule components will appear here after analysis...")
        evidence_layout.addWidget(self.evidence_output)
        right_layout.addWidget(evidence_card)
        
        stats_card = QFrame()
        stats_card.setObjectName("card")
        stats_layout = QVBoxLayout(stats_card)
        stats_label = QLabel("Final Diagnosis")
        stats_label.setStyleSheet("font-weight: 700; font-size: 13px;")
        stats_layout.addWidget(stats_label)
        self.stats_area = QLabel("Nerves analyzed: 0\nMain diagnoses: -")
        self.stats_area.setStyleSheet("font-size: 13px; color: #2C2C2E;")
        stats_layout.addWidget(self.stats_area)
        right_layout.addWidget(stats_card)
        right_layout.addStretch(1)
        
        # Right side wrapped in a scroll area so panels auto-adapt
        right_scroll = QScrollArea()
        right_scroll.setWidgetResizable(True)
        right_scroll.setFrameShape(QFrame.Shape.NoFrame)
        right_scroll.setWidget(right_container)

        splitter.addWidget(left_scroll)
        splitter.addWidget(right_scroll)
        
        card_layout.addWidget(splitter)
        central_layout.addWidget(card)
        main_layout.addWidget(central_container, stretch=9)
        
        footer = QHBoxLayout()
        footer_label = QLabel("Developed by prof. Antonio Rescifina and Dr. Rocco Buccheri at Catania University")
        footer_label.setObjectName("footer")
        footer.addStretch(1)
        footer.addWidget(footer_label)
        footer.addStretch(1)
        main_layout.addLayout(footer, stretch=1)

    def setup_file_tab(self):
        # ... (invariato) ...
        layout = QVBoxLayout(self.file_tab)
        tab_card = QFrame()
        tab_card.setObjectName("card")
        tab_layout = QVBoxLayout(tab_card)
        info_label = QLabel("Select a .doc/.docx file to extract data automatically.")
        info_label.setStyleSheet("color: #6E6E73;")
        tab_layout.addWidget(info_label)
        self.file_tables = {}
        for key, headers in self.MANUAL_HEADERS.items():
            group = QGroupBox(f"{key.title()} Nerves")
            group_layout = QVBoxLayout()
            table = QTableWidget(0, len(headers) + 1)
            table.setHorizontalHeaderLabels(headers + ["Diagnosis"])
            # First column (Nerve name) auto-sizes; rest are interactive
            table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
            for col in range(1, len(headers) + 1):
                table.horizontalHeader().setSectionResizeMode(col, QHeaderView.ResizeMode.Interactive)
            table.horizontalHeader().setStretchLastSection(True)
            table.setSizeAdjustPolicy(QTableWidget.SizeAdjustPolicy.AdjustToContents)
            table.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.MinimumExpanding)
            table.itemChanged.connect(self.run_analysis)
            self.file_tables[key] = table
            group_layout.addWidget(table)
            group.setLayout(group_layout)
            tab_layout.addWidget(group)
        tab_layout.addStretch(1)
        layout.addWidget(tab_card)

    def setup_manual_tab(self):
        # ... (invariato) ...
        layout = QVBoxLayout(self.manual_tab)
        tab_card = QFrame()
        tab_card.setObjectName("card")
        tab_layout = QVBoxLayout(tab_card)
        self.manual_tables = {}
        for key, headers in self.MANUAL_HEADERS.items():
            group = QGroupBox(f"{key.title()} Nerves")
            group_layout = QVBoxLayout()
            add_button = QPushButton(f"⚪ Add {key.title()} Nerve")
            add_button.clicked.connect(lambda _, k=key: self.open_nerve_selection_dialog(k))
            table = QTableWidget(0, len(headers))
            table.setHorizontalHeaderLabels(headers)
            table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
            for col in range(1, len(headers)):
                table.horizontalHeader().setSectionResizeMode(col, QHeaderView.ResizeMode.Interactive)
            table.horizontalHeader().setStretchLastSection(True)
            table.setSizeAdjustPolicy(QTableWidget.SizeAdjustPolicy.AdjustToContents)
            table.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.MinimumExpanding)
            table.itemChanged.connect(self.run_analysis)
            self.manual_tables[key] = table
            group_layout.addWidget(add_button)
            group_layout.addWidget(table)
            group.setLayout(group_layout)
            tab_layout.addWidget(group)
        tab_layout.addStretch(1)
        layout.addWidget(tab_card)
    
    def add_manual_row(self, key):
        # ... (invariato) ...
        table = self.manual_tables[key]
        row_count = table.rowCount()
        table.insertRow(row_count)

    def load_settings(self):
        self.all_settings = {"Native Defaults": copy.deepcopy(self.DEFAULT_SETTINGS)}
        
        # Inizializza la variabile per tracciare il default corrente
        self.current_default_preset = "Native Defaults" 

        if os.path.exists(self.SETTINGS_FILE):
            try:
                with open(self.SETTINGS_FILE, 'r') as f:
                    saved_data = json.load(f)
                    
                    # --- MODIFICA QUI ---
                    for key, value in saved_data.items():
                        # Escludi sia Native Defaults che la chiave speciale __default__
                        if key != "Native Defaults" and key != "__default__":
                            self.all_settings[key] = value
                    
                    # Recupera il default separatamente
                    if "__default__" in saved_data and saved_data["__default__"] in self.all_settings:
                        self.current_default_preset = saved_data["__default__"]
                    # --------------------
                        
            except Exception as e:
                print(f"Errore nel caricamento di {self.SETTINGS_FILE}: {e}")
        
        # Usa la variabile di classe aggiornata
        self.settings = copy.deepcopy(self.all_settings[self.current_default_preset])

    def save_settings_to_file(self, all_settings_data, new_default=None):
        self.all_settings = all_settings_data
        
        # Aggiorna la variabile interna se viene passato un nuovo default
        if new_default:
            self.current_default_preset = new_default
        
        # Se la variabile non esiste (caso primo avvio/errore), inizializzala
        if not hasattr(self, "current_default_preset"):
            self.current_default_preset = "Native Defaults"

        try:
            # Crea una copia per il salvataggio per non sporcare self.all_settings
            data_to_save = self.all_settings.copy()
            # Scrive esplicitamente la chiave __default__ nel JSON
            data_to_save["__default__"] = self.current_default_preset
            
            with open(self.SETTINGS_FILE, 'w') as f:
                json.dump(data_to_save, f, indent=4)
        except Exception as e:
            print(f"Error saving {self.SETTINGS_FILE}: {e}")
            QMessageBox.warning(self, "Save Error", f"Could not save settings to {self.SETTINGS_FILE}:\n{e}")

    def open_settings_dialog(self):
        """Open reference settings and immediately refresh the current analysis when they change."""
        previous_settings = copy.deepcopy(self.settings)
        dialog = SettingsDialog(copy.deepcopy(self.settings), copy.deepcopy(self.all_settings), self)
        if dialog.exec():
            self.all_settings = copy.deepcopy(dialog.all_settings)
            self.settings = dialog.get_session_settings()
            if self.settings != previous_settings:
                self.run_analysis()
                self.statusBar().showMessage("Reference settings applied; diagnostic output refreshed.", 6000)
            else:
                self.statusBar().showMessage("Reference settings unchanged.", 4000)
        else:
            current_preset_name = self.find_preset_name(self.settings)
            self.settings = copy.deepcopy(self.all_settings[current_preset_name])

    def find_preset_name(self, settings_to_find):
        # ... (invariato) ...
        for name, preset in self.all_settings.items():
            if preset == settings_to_find:
                return name
        return "Native Defaults" 

    @staticmethod
    def _clean_numeric_value(raw: str) -> str:
        """
        If 'raw' contains multiple numbers separated by whitespace or newlines,
        return only the first numeric token.  Non-numeric strings are returned
        unchanged so that nerve names are never mangled.
        """
        import re
        if not raw:
            return raw
        # Split on any whitespace (spaces, tabs, newlines)
        tokens = raw.split()
        if len(tokens) <= 1:
            return raw
        # Return the first token that looks like a number (int or float, optional sign)
        number_pattern = re.compile(r'^[+-]?\d+([.,]\d+)?$')
        for token in tokens:
            if number_pattern.match(token):
                return token
        # No numeric token found – return first token as fallback
        return tokens[0]

    def load_file(self):
        # ... (invariato) ...
        filepath, _ = QFileDialog.getOpenFileName(self, "Open File", "", "Word Documents (*.doc *.docx)")
        if filepath:
            self.load_button.setText("Loading...")
            self.load_button.setEnabled(False)
            worker = FileProcessor(filepath)
            worker.signals.finished.connect(self.on_file_load_finished)
            worker.signals.error.connect(self.on_file_load_error)
            self.threadpool.start(worker)

    def on_file_load_error(self, error_message):
        self.load_button.setText("📂 Select File")
        self.load_button.setEnabled(True)
        QMessageBox.warning(self, "File Load Error", str(error_message))

    def on_file_load_finished(self, extracted_data):
        # ... (invariato) ...
        self.load_button.setText("📂 Select File")
        self.load_button.setEnabled(True)
        for key, data_list in extracted_data.items():
            if key not in self.file_tables: continue
            table = self.file_tables[key]
            table.setRowCount(len(data_list))
            headers = self.MANUAL_HEADERS[key]
            diag_col_idx = len(headers)
            for row_idx, row_data in enumerate(data_list):
                for col_idx, header in enumerate(headers):
                    key_to_get = header
                    if header == "F / M (%)":
                        key_to_get = "Persist"
                    elif header in ("DML [ms]",):
                        key_to_get = "DML"
                    raw_value = str(row_data.get(key_to_get, ""))
                    # For numeric columns (all except the first "Nerve" column),
                    # keep only the first numeric token if multiple values are present.
                    if col_idx > 0:
                        raw_value = self._clean_numeric_value(raw_value)
                    item = QTableWidgetItem(raw_value)
                    table.setItem(row_idx, col_idx, item)
                placeholder_item = QTableWidgetItem("")
                placeholder_item.setFlags(placeholder_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                table.setItem(row_idx, diag_col_idx, placeholder_item)
        self.run_analysis()

    def _on_pediatric_toggled(self, is_pediatric: bool):
        """Switch between Adult and Pediatric input modes."""
        self.pediatric_mode = is_pediatric

        if is_pediatric:
            self.mode_toggle_btn.setText("Switch to Adult Mode")
            self.mode_toggle_btn.setToolTip(
                "Currently: Pediatric Mode (0–14 months)\n"
                "Click to switch back to Adult Mode"
            )
        else:
            self.mode_toggle_btn.setText("Switch to Pediatric Mode")
            self.mode_toggle_btn.setToolTip(
                "Currently: Adult Mode\n"
                "Click to switch to Pediatric Mode (0–14 months)"
            )

        # Adult inputs: visible only in adult mode
        self.lbl_age.setVisible(not is_pediatric)
        self.age_spin.setVisible(not is_pediatric)
        self.lbl_height.setVisible(not is_pediatric)
        self.height_spin.setVisible(not is_pediatric)

        # Pediatric inputs: visible only in pediatric mode
        self.lbl_age_months.setVisible(is_pediatric)
        self.age_months_spin.setVisible(is_pediatric)

        self.run_analysis()

    def get_data_from_tables(self, tables):
        # ... (invariato) ...
        all_data = {}
        for key, table in tables.items():
            data_list = []
            headers = [table.horizontalHeaderItem(i).text() for i in range(table.columnCount())]
            for r in range(table.rowCount()):
                row_data = {}
                for c, header in enumerate(headers):
                    if header == "Diagnosis": continue
                    key_to_save = header
                    if header == "F / M (%)":
                        key_to_save = "Persist"
                    elif header in ("DML [ms]",):
                        key_to_save = "DML"
                    item = table.item(r, c)
                    if item and item.text():
                        cell_text = item.text()
                        # For numeric columns (all except the first "Nerve" column),
                        # keep only the first numeric token if multiple values are present.
                        if c > 0:
                            cell_text = self._clean_numeric_value(cell_text)
                        row_data[key_to_save] = cell_text
                    else:
                        row_data[key_to_save] = ""
                if row_data.get("Nerve"):
                    data_list.append(row_data)
            all_data[key] = data_list
        return all_data

    def _active_reference_overrides(self):
        """Return GUI reference overrides only when a non-native preset is active.

        This prevents the generic GUI defaults from overriding the built-in
        nerve-specific database unless the user explicitly selects/saves a
        custom preset.
        """
        if self.settings == self.DEFAULT_SETTINGS:
            return None
        return self.settings

    def _update_evidence_panel(self, results):
        lines = []
        for modality in ("motor", "sensory", "fwave"):
            for rec in results.get(modality, []):
                ev = rec.get("evidence", {})
                z = ev.get("z_scores", {}) if isinstance(ev, dict) else {}
                z_txt = ", ".join(
                    f"z{key}={value:.2f}" for key, value in z.items() if isinstance(value, (int, float))
                )
                override = " | custom refs" if ev.get("reference_override_applied") else ""
                if z_txt:
                    lines.append(f"{modality.title()} — {rec.get('nerve', '-')}: {rec.get('diagnosis', '-')} ({z_txt}{override})")
                else:
                    lines.append(f"{modality.title()} — {rec.get('nerve', '-')}: {rec.get('diagnosis', '-')}{override}")
        self.evidence_output.setText("\n".join(lines[:60]) if lines else "No analyzable evidence yet.")

    def export_report(self):
        if not self.latest_results or not any(self.latest_results.get(k) for k in ("motor", "sensory", "fwave")):
            QMessageBox.information(self, "Export Report", "No analysis results are available yet.")
            return
        tables_to_use = self.file_tables if self.tabs.currentIndex() == 0 else self.manual_tables
        data_to_analyze = self.get_data_from_tables(tables_to_use)
        validation = validate_exam(data_to_analyze['motor'], data_to_analyze['sensory'], data_to_analyze['fwave'])
        context = {
            "mode": "pediatric" if self.pediatric_mode else "adult",
            "age_years": self.age_spin.value() if not self.pediatric_mode else "-",
            "age_months": self.age_months_spin.value() if self.pediatric_mode else "-",
            "height_cm": self.height_spin.value(),
            "custom_reference_override": self._active_reference_overrides() is not None,
        }
        path, _ = QFileDialog.getSaveFileName(self, "Export NeuroScan Report", "neuroscan_report.txt", "Text Files (*.txt)")
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(build_text_report(self.latest_results, validation=validation, patient_context=context))
            QMessageBox.information(self, "Export Report", f"Report exported to:\n{path}")
        except Exception as exc:
            QMessageBox.warning(self, "Export Error", f"Could not export report:\n{exc}")

    def export_html_report_with_graphs(self):
        if not self.latest_results or not any(self.latest_results.get(k) for k in ("motor", "sensory", "fwave")):
            QMessageBox.information(self, "Report + Graphs", "No analysis results are available yet.")
            return
        tables_to_use = self.file_tables if self.tabs.currentIndex() == 0 else self.manual_tables
        data_to_analyze = self.get_data_from_tables(tables_to_use)
        validation = validate_exam(data_to_analyze['motor'], data_to_analyze['sensory'], data_to_analyze['fwave'])
        context = {
            "mode": "pediatric" if self.pediatric_mode else "adult",
            "age_years": self.age_spin.value() if not self.pediatric_mode else "-",
            "age_months": self.age_months_spin.value() if self.pediatric_mode else "-",
            "height_cm": self.height_spin.value(),
            "custom_reference_override": self._active_reference_overrides() is not None,
        }
        path, _ = QFileDialog.getSaveFileName(self, "Export Printable NeuroScan Report", "neuroscan_report_with_graphs.html", "HTML Files (*.html)")
        if not path:
            return
        if not path.lower().endswith(".html"):
            path += ".html"
        try:
            if self.plot_dialog is None:
                self.plot_dialog = AnalysisPlotDialog(self.latest_results, parent=self)
            self.plot_dialog.update_data(self.latest_results)
            figure_bytes = self.plot_dialog.combined_figure_png_bytes()
            html = build_html_report(self.latest_results, validation=validation, patient_context=context, figure_png_bytes=figure_bytes)
            with open(path, "w", encoding="utf-8") as f:
                f.write(html)
            QMessageBox.information(self, "Report + Graphs", f"Printable HTML report exported to:\n{path}")
        except Exception as exc:
            QMessageBox.warning(self, "Export Error", f"Could not export report with graphs:\n{exc}")

    def run_phase2_batch_builder(self):
        input_dir = QFileDialog.getExistingDirectory(self, "Select folder containing original DOCX reports")
        if not input_dir:
            return
        output_dir = QFileDialog.getExistingDirectory(self, "Select output folder for the Phase-2 validation package")
        if not output_dir:
            return
        try:
            summary = build_validation_dataset(input_dir, output_dir)
            QMessageBox.information(
                self,
                "Phase 2 Batch Builder",
                "Phase-2 validation package completed.\n\n"
                f"Files processed: {summary.get('files_processed')}\n"
                f"Reports folder: {summary.get('reports_dir')}\n"
                f"SQLite archive: {summary.get('sqlite_path')}\n"
                f"Review-required flags: {summary.get('review_required')}"
            )
        except Exception as exc:
            QMessageBox.warning(self, "Phase 2 Batch Builder", f"Batch processing failed:\n{exc}")

    def reanalyze_current_data(self):
        """Explicitly re-run the diagnostic pipeline on the current tables."""
        self.run_analysis()
        self.statusBar().showMessage("Diagnostic output refreshed using current reference settings.", 6000)

    def run_analysis(self):
        tables_to_use = self.file_tables if self.tabs.currentIndex() == 0 else self.manual_tables
        data_to_analyze = self.get_data_from_tables(tables_to_use)

        age = self.age_spin.value()
        height = self.height_spin.value()
        age_months = self.age_months_spin.value() if self.pediatric_mode else None

        # 1. Run analysis
        results = analyze_data(
            data_to_analyze['motor'],
            data_to_analyze['sensory'],
            data_to_analyze['fwave'],
            age, height,
            pediatric_mode=self.pediatric_mode,
            age_months=age_months,
            reference_overrides=self._active_reference_overrides()
        )
        
        # --- CORREZIONE CRITICA ---
        # Aggiorniamo la cache dei risultati SUBITO, prima di qualsiasi altra operazione.
        # Se questo viene fatto dopo update_summary, la diagnosi mostrerà i dati vecchi.
        self.latest_results = results 
        # --------------------------

        all_diagnoses = []
        for key in ('motor', 'sensory', 'fwave'):
            for nerve_data in results[key]:
                all_diagnoses.append(nerve_data['diagnosis'])

        # Aggiorna le tabelle (GUI)
        for key, nerve_list in ((k, results[k]) for k in ('motor', 'sensory', 'fwave')):
            table = tables_to_use[key]
            table.blockSignals(True) # Fondamentale per evitare loop
            try:
                if table.columnCount() <= len(self.MANUAL_HEADERS[key]):
                    table.insertColumn(len(self.MANUAL_HEADERS[key]))
                    table.setHorizontalHeaderItem(len(self.MANUAL_HEADERS[key]), QTableWidgetItem("Diagnosis"))
                
                diag_col_idx = table.columnCount() - 1
                for row_idx, nerve_data in enumerate(nerve_list):
                    diagnosis = nerve_data['diagnosis'] 
                    item = QTableWidgetItem(diagnosis)
                    item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                    
                    if "|" in diagnosis:
                        item.setForeground(QColor(200, 100, 0))
                    elif "Missing data" in diagnosis:
                        item.setForeground(QColor(231, 76, 60))
                    
                    table.setItem(row_idx, diag_col_idx, item)
            finally:
                table.blockSignals(False)

        # 2. Update summary and Final Diagnosis
        self.update_summary(all_diagnoses)

        # 3. Run exam validation and update validation panel
        validation = validate_exam(
            data_to_analyze['motor'],
            data_to_analyze['sensory'],
            data_to_analyze['fwave']
        )
        self._update_validation_panel(validation)
        self._update_evidence_panel(results)

        # 4. Update graphs if open
        if self.plot_dialog is not None and self.plot_dialog.isVisible():
            self.plot_dialog.update_data(self.latest_results)
    
    def open_graphs_window(self):
        """Gestisce l'apertura o il focus della finestra dei grafici."""

        if self.plot_dialog is None:
            # Crea l'istanza se non esiste (passando self come parent per mantenerla sopra)
            self.plot_dialog = AnalysisPlotDialog(self.latest_results, parent=self)
            # Gestione della chiusura per non distruggere l'oggetto (opzionale, ma utile)
            self.plot_dialog.finished.connect(lambda: None) 
        
        # Se esiste ma è stata chiusa o nascosta, o se bisogna aggiornarla
        if not self.plot_dialog.isVisible():
            self.plot_dialog.update_data(self.latest_results)
            self.plot_dialog.show() # .show() invece di .exec() per non bloccare
        else:
            # Se è già visibile, portala in primo piano
            self.plot_dialog.raise_()
            self.plot_dialog.activateWindow()

    def update_summary(self, all_diagnoses_flat):
        """
        Updates the summary panel and Final Diagnosis box.
        Uses ESTEEM Table 2 criteria for PNP classification via classify_pnp().
        """
        # --- 1. Update "Diagnosis Summary" panel ---
        if not all_diagnoses_flat:
            self.summary_output.setText("No data to analyze.")
            self.stats_area.setText("Waiting for analysis...")
            return

        total_nerves = len(all_diagnoses_flat)
        counts = Counter(all_diagnoses_flat)
        summary_text = f"<b>Total {total_nerves} nerves analyzed.</b><br><br>"
        summary_text += "<b>Details per nerve:</b><br>"
        for diagnosis, count in counts.most_common():
            percentage = (count / total_nerves) * 100
            summary_text += f"• {percentage:.0f}% {diagnosis} ({count})<br>"
        self.summary_output.setText(summary_text)

        # --- 2. Group-level diagnosis (per modality) ---
        motor_diag = self._calculate_group_diagnosis(self.latest_results['motor'])
        sensory_diag = self._calculate_group_diagnosis(self.latest_results['sensory'])
        fwave_diag = self._calculate_group_diagnosis(self.latest_results['fwave'])

        # --- 3. Patient-level PNP classification (ESTEEM Table 2) ---
        # Use the pre-computed classification from analyze_data if available,
        # otherwise compute it now.
        pnp_info = self.latest_results.get('pnp_classification')
        if pnp_info is None:
            pnp_info = classify_pnp(
                self.latest_results['motor'],
                self.latest_results['sensory'],
                self.latest_results['fwave']
            )

        pnp_pattern = pnp_info.get('pattern', 'Unclassified')
        pnp_details = pnp_info.get('details', '')

        # --- 4. Color coding ---
        def color_for_group(text):
            if text == "Normal":   return "#27AE60"   # Green
            if text == "N/A":      return "#95A5A6"   # Grey
            if text == "Mixed":    return "#D35400"   # Dark orange
            if "Demyelinating" in text or "demyelinating" in text:
                return "#E67E22"  # Orange
            if "Axonal" in text:   return "#C0392B"   # Red
            return "#8E44AD"  # Purple for Neuropathic/other

        def color_for_pnp(pattern):
            if pattern == "Normal":        return "#27AE60"
            if pattern == "Demyelinating": return "#E67E22"
            if pattern == "Axonal":        return "#C0392B"
            if pattern == "Mixed":         return "#D35400"
            if "N/A" in pattern:           return "#95A5A6"
            return "#8E44AD"  # Neuropathic / Unclassified

        stats_html = f"""
        <html>
        <body style='font-family:-apple-system, sans-serif; font-size:13px;'>

            <div style='margin-bottom: 4px;'>
                <b>Motor Nerves:</b>
                <span style='color:{color_for_group(motor_diag)}'>{motor_diag}</span>
            </div>
            <div style='margin-bottom: 4px;'>
                <b>Sensory Nerves:</b>
                <span style='color:{color_for_group(sensory_diag)}'>{sensory_diag}</span>
            </div>
            <div style='margin-bottom: 12px;'>
                <b>F-Wave Nerves:</b>
                <span style='color:{color_for_group(fwave_diag)}'>{fwave_diag}</span>
            </div>

            <hr style='border: 0; border-top: 1px solid #ddd; margin: 5px 0;'>

            <div style='margin-top: 8px;'>
                <b style='font-size:14px; color:#2C3E50;'>PNP Classification</b>
                <span style='font-size:10px; color:#7F8C8D;'> (ESTEEM Table 2)</span><br>
                <div style='margin-top:4px;'>
                    Pattern: <span style='font-weight:bold; color:{color_for_pnp(pnp_pattern)};'>
                        {pnp_pattern}
                    </span>
                </div>
                <div style='margin-top:6px; color:#555; font-size:11px;'>
                    {pnp_details}
                </div>
            </div>

        </body>
        </html>
        """

        self.stats_area.setText(stats_html)

    def _update_validation_panel(self, validation):
        """Renders the exam validation result in the sidebar panel."""
        errors   = validation.get('errors', [])
        warnings = validation.get('warnings', [])
        coverage = validation.get('coverage', {})

        if not errors and not warnings:
            html = "<span style='color:#27AE60; font-weight:bold;'>✅ Exam complete.</span> "\
                   "All minimum ESTEEM nerve requirements are met."
        else:
            parts = []
            for e in errors:
                parts.append(f"<span style='color:#C0392B;'>❌ {e}</span>")
            for w in warnings:
                parts.append(f"<span style='color:#E67E22;'>⚠️ {w}</span>")
            html = "<br>".join(parts)

        # Coverage table
        if coverage:
            html += "<br><br><b>Coverage:</b><br>"
            for modality, nerves in coverage.items():
                for nerve, present in nerves.items():
                    icon = "✅" if present else "☐"
                    html += f"{icon} {modality.title()} {nerve.title()}&nbsp;&nbsp;"
                html += "<br>"

        self.validation_output.setText(html)
        self.validation_output.setTextFormat(Qt.TextFormat.RichText)

    def open_nerve_selection_dialog(self, key):
        # Passiamo 'key' al costruttore in modo che sappia quali liste mostrare
        dialog = NerveSelectionDialog(nerve_type=key, parent=self)
        
        if dialog.exec():
            selected_nerves = dialog.get_selected_nerves()
            table = self.manual_tables[key]
            for nerve_name in selected_nerves:
                row_count = table.rowCount()
                table.insertRow(row_count)
                nerve_item = QTableWidgetItem(nerve_name)
                table.setItem(row_count, 0, nerve_item)
    
    def _calculate_group_diagnosis(self, nerve_list):
        """
        Calculates the predominant diagnosis for a group of nerves (motor/sensory/fwave).
        Returns 'N/A' if no valid data is available.

        Demyelinating findings are kept as their own category (not collapsed into
        Neuropathic), since they are clinically distinct and used by classify_pnp().
        """
        valid_diagnoses = []

        for nerve in nerve_list:
            raw_diag = nerve['diagnosis']
            if raw_diag in ["Missing data", "Analysis Error", "N/A"]:
                continue

            # Normalize split diagnoses ("CV: X | DML: Y") to the more severe one
            if "|" in raw_diag:
                parts = [p.strip().split(": ", 1)[-1] for p in raw_diag.split("|")]
                severity_order = [
                    "Normal", "Axonal loss", "Neuropathic",
                    "Re/demyelinating (Probable)", "Re/demyelinating (Definite)"
                ]
                best = max(parts, key=lambda d: severity_order.index(d)
                           if d in severity_order else 2)
                valid_diagnoses.append(best)
            else:
                valid_diagnoses.append(raw_diag)

        if not valid_diagnoses:
            return "N/A"

        total_valid = len(valid_diagnoses)
        counts = Counter(valid_diagnoses)
        most_common_diag, count = counts.most_common(1)[0]

        if count >= (total_valid / 2.0):
            return most_common_diag

        return "Mixed"

def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
