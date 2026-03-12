import sys
import os
import sqlite3
import csv
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                               QHBoxLayout, QTableView, QLabel, QLineEdit, 
                               QPushButton, QGroupBox, QHeaderView, QFormLayout, 
                               QMessageBox, QAbstractItemView, QTabWidget, QFileDialog)
from PySide6.QtCore import Qt, QAbstractTableModel, QModelIndex
from PySide6.QtGui import QIcon

import matplotlib.pyplot as plt
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg

def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

def init_db():
    if getattr(sys, 'frozen', False):
        script_dir = os.path.dirname(sys.executable)
    else:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        
    db_path = os.path.join(script_dir, "tourism_commerce.db")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            cost REAL,
            price REAL,
            qty INTEGER
        )
    ''')
    cursor.execute("SELECT COUNT(*) FROM products")
    if cursor.fetchone()[0] == 0:
        starter_data = [
            ("Luxury Suite (Nightly)", 120.0, 350.0, 45),
            ("All-Day Vineyard Tour", 45.0, 115.0, 120),
            ("Artisan Leather Handbag", 65.0, 185.0, 30),
            ("Airport VIP Shuttle", 25.0, 60.0, 85)
        ]
        cursor.executemany("INSERT INTO products (name, cost, price, qty) VALUES (?, ?, ?, ?)", starter_data)
        conn.commit()
    return conn

class ProductTableModel(QAbstractTableModel):
    def __init__(self, conn):
        super().__init__()
        self.conn = conn
        self._headers = ["#", "Product Name", "Unit Cost ($)", "Price ($)", "Expected Qty", "Revenue ($)", "Profit ($)"]
        self._data = []
        self.load_data()

    def load_data(self):
        self.beginResetModel()
        cursor = self.conn.cursor()
        cursor.execute("SELECT id, name, cost, price, qty FROM products ORDER BY id ASC")
        rows = cursor.fetchall()
        self._data = [list(row) + [0, 0] for row in rows]
        self.recalculate_totals()
        self.endResetModel()

    def recalculate_totals(self):
        for row in self._data:
            cost, price, qty = row[2], row[3], row[4]
            row[5] = round(price * qty, 2)
            row[6] = round((price - cost) * qty, 2)

    def data(self, index, role):
        if role == Qt.ItemDataRole.DisplayRole or role == Qt.ItemDataRole.EditRole:
            if index.column() == 0:
                return index.row()
            return self._data[index.row()][index.column()]
        
        if role == Qt.ItemDataRole.ForegroundRole and index.column() == 6:
            profit = self._data[index.row()][6]
            return Qt.GlobalColor.darkGreen if profit >= 0 else Qt.GlobalColor.red

    def setData(self, index, value, role):
        if role == Qt.ItemDataRole.EditRole:
            col, row_idx = index.column(), index.row()
            product_id = self._data[row_idx][0]
            try:
                new_value = float(value) if col in [2, 3] else int(value)
                self._data[row_idx][col] = new_value
                self.recalculate_totals()
                
                cursor = self.conn.cursor()
                if col == 2:   cursor.execute("UPDATE products SET cost = ? WHERE id = ?", (new_value, product_id))
                elif col == 3: cursor.execute("UPDATE products SET price = ? WHERE id = ?", (new_value, product_id))
                elif col == 4: cursor.execute("UPDATE products SET qty = ? WHERE id = ?", (new_value, product_id))
                self.conn.commit()

                self.dataChanged.emit(self.index(row_idx, 0), self.index(row_idx, 6))
                return True
            except ValueError:
                return False
        return False

    def add_product(self, name, cost, price, qty):
        cursor = self.conn.cursor()
        cursor.execute("INSERT INTO products (name, cost, price, qty) VALUES (?, ?, ?, ?)", (name, cost, price, qty))
        self.conn.commit()
        self.load_data()

    def delete_product(self, row_index):
        product_id = self._data[row_index][0]
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM products WHERE id = ?", (product_id,))
        self.conn.commit()
        self.load_data()

    def rowCount(self, index=QModelIndex()): return len(self._data)
    def columnCount(self, index=QModelIndex()): return len(self._headers)
    
    def headerData(self, section, orientation, role):
        if role == Qt.ItemDataRole.DisplayRole and orientation == Qt.Orientation.Horizontal:
            return self._headers[section]

    def flags(self, index):
        if index.column() in [2, 3, 4]:
            return Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsEditable
        return Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled


class RevenueManagerApp(QMainWindow):
    def __init__(self, db_conn):
        super().__init__()
        self.setWindowTitle("Revenue Manager & Analytics")
        self.setWindowIcon(QIcon(resource_path("icon.ico")))
        self.resize(1100, 600)
        
        script_dir = os.path.dirname(os.path.abspath(__file__))
        icon_path = os.path.join(script_dir, "icon.ico")
        
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
        else:
            print(f"Warning: Icon not found at {icon_path}")

        self.model = ProductTableModel(db_conn)
        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)

        self.setup_data_tab()
        self.setup_visualization_tab()
        
        self.tabs.currentChanged.connect(self.on_tab_changed)
        self.model.dataChanged.connect(self.draw_chart)
        self.model.modelReset.connect(self.draw_chart)   
        self.draw_chart()

    def setup_data_tab(self):
        self.tab1 = QWidget()
        main_layout = QHBoxLayout(self.tab1)
        left_layout = QVBoxLayout()
        
        self.table_view = QTableView()
        self.table_view.setModel(self.model)
        self.table_view.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        
        self.table_view.setAlternatingRowColors(True)
        self.table_view.setStyleSheet("""
            QTableView {
                selection-background-color: #0078D7;
                selection-color: white;
            }
        """)
        left_layout.addWidget(self.table_view)

        mgmt_group = QGroupBox("Manage Products")
        mgmt_layout = QHBoxLayout()
        
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("Product Name")
        self.cost_input = QLineEdit()
        self.cost_input.setPlaceholderText("Unit Cost")
        self.price_input = QLineEdit()
        self.price_input.setPlaceholderText("Selling Price")
        self.qty_input = QLineEdit()
        self.qty_input.setPlaceholderText("Expected Qty")
        
        add_btn = QPushButton("Add")
        add_btn.clicked.connect(self.handle_add_product)
        
        del_btn = QPushButton("Delete")
        del_btn.setStyleSheet("background-color: #d9534f; color: white;")
        del_btn.clicked.connect(self.handle_delete_product)

        export_btn = QPushButton("Export CSV")
        export_btn.setStyleSheet("background-color: #5cb85c; color: white;")
        export_btn.clicked.connect(self.export_to_csv)

        for widget in [self.name_input, self.cost_input, self.price_input, self.qty_input, add_btn, del_btn, export_btn]:
            mgmt_layout.addWidget(widget)
        
        mgmt_group.setLayout(mgmt_layout)
        left_layout.addWidget(mgmt_group)
        main_layout.addLayout(left_layout, stretch=3)

        calc_group = QGroupBox("Price Elasticity Calculator")
        calc_layout = QFormLayout()
        self.p1_input = QLineEdit("100")
        self.p2_input = QLineEdit("110")
        self.q1_input = QLineEdit("500")
        self.q2_input = QLineEdit("420")
        
        calc_layout.addRow("Old Price (P1):", self.p1_input)
        calc_layout.addRow("New Price (P2):", self.p2_input)
        calc_layout.addRow("Old Qty (Q1):", self.q1_input)
        calc_layout.addRow("New Qty (Q2):", self.q2_input)

        calc_btn = QPushButton("Calculate PED")
        calc_btn.clicked.connect(self.calculate_elasticity)
        calc_layout.addRow(calc_btn)

        self.result_label = QLabel("PED: --\nInterpretation: --")
        calc_layout.addRow(self.result_label)

        calc_group.setLayout(calc_layout)
        main_layout.addWidget(calc_group, stretch=1)
        
        self.tabs.addTab(self.tab1, "Data & Management")

    def setup_visualization_tab(self):
        self.tab2 = QWidget()
        layout = QVBoxLayout(self.tab2)
        self.figure = plt.figure(figsize=(8, 5))
        self.figure.patch.set_alpha(0.0) 
        
        self.canvas = FigureCanvasQTAgg(self.figure)
        layout.addWidget(self.canvas)
        self.tabs.addTab(self.tab2, "Revenue Visualization")

    def on_tab_changed(self, index):
        if index == 1:
            self.draw_chart()

    def draw_chart(self):
        self.figure.clear()
        ax = self.figure.add_subplot(111)
        names = [row[1] for row in self.model._data]
        revenues = [row[5] for row in self.model._data]
        
        if not names:
            self.canvas.draw()
            return
            
        bars = ax.bar(names, revenues, color='#2ca02c')
        ax.set_title("Total Expected Revenue by Product", fontsize=14, pad=15)
        ax.set_ylabel("Revenue ($)", fontsize=12)
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        plt.xticks(rotation=25, ha='right')
        ax.bar_label(bars, fmt='$%.2f', padding=3)
        self.figure.tight_layout()
        self.canvas.draw()

    def handle_add_product(self):
        name = self.name_input.text()
        try:
            cost, price = float(self.cost_input.text()), float(self.price_input.text())
            qty = int(self.qty_input.text())
            if not name: raise ValueError("Name empty.")
            self.model.add_product(name, cost, price, qty)
            for widget in [self.name_input, self.cost_input, self.price_input, self.qty_input]:
                widget.clear()
        except ValueError:
             QMessageBox.warning(self, "Input Error", "Please ensure Cost and Price are numbers, and Qty is a whole number.")

    def handle_delete_product(self):
        selected_indexes = self.table_view.selectionModel().selectedIndexes()
        if not selected_indexes:
            QMessageBox.information(self, "Error", "Click on any cell in the row you want to delete first.")
            return
        row_to_delete = selected_indexes[0].row()
        self.model.delete_product(row_to_delete)

    def export_to_csv(self):
        file_path, _ = QFileDialog.getSaveFileName(self, "Save Financial Report", "Tourism_Revenue_Report.csv", "CSV Files (*.csv)")
        if file_path:
            try:
                with open(file_path, mode='w', newline='', encoding='utf-8') as file:
                    writer = csv.writer(file)
                    writer.writerow(self.model._headers)
                    writer.writerows(self.model._data)
                QMessageBox.information(self, "Success", f"Report successfully saved to:\n{file_path}")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to save file.\nError: {e}")

    def calculate_elasticity(self):
        try:
            p1, p2 = float(self.p1_input.text()), float(self.p2_input.text())
            q1, q2 = float(self.q1_input.text()), float(self.q2_input.text())
            if p1 == 0 or q1 == 0: raise ZeroDivisionError

            pct_change_q = (q2 - q1) / q1
            pct_change_p = (p2 - p1) / p1
            ped = abs(pct_change_q / pct_change_p)

            if ped > 1: interp = "Elastic (Revenue drops if price rises)"
            elif ped < 1: interp = "Inelastic (Safe to raise prices)"
            else: interp = "Unitary Elasticity"

            self.result_label.setText(f"PED: {ped:.2f}\n{interp}")
        except:
            QMessageBox.warning(self, "Error", "Invalid numbers.")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    db_conn = init_db() 
    window = RevenueManagerApp(db_conn)
    window.show()
    exit_code = app.exec()
    db_conn.close()
    sys.exit(exit_code)