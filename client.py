import json
import logging
import sys
import random
import os
import pygame  # 导入用于播放音频的pygame模块


from PyQt5.QtCore import QByteArray, QTimer, QDateTime
from PyQt5.QtGui import QIcon, QFont
from PyQt5.QtNetwork import QTcpSocket, QAbstractSocket
from PyQt5.QtWidgets import QMainWindow, QApplication, QLabel, QVBoxLayout, QWidget, QPushButton, QTextEdit, \
    QInputDialog, QSystemTrayIcon, QMenu, QAction, QMessageBox
from qt_material import apply_stylesheet


class Client(QMainWindow):
    def __init__(self, host, port, role):
        super(Client, self).__init__()
        self.host = host
        self.port = port
        self.role = role
        print(f"Role on init: {self.role}")
        self.emotions = {'he': "😊", 'she': "😊"}
        self.init_ui()
        self.init_socket()
        self.update_emotion_status()
        print(f"Role on init: {self.role}")


    def init_ui(self):
        # 标题根据角色设置
        self.setWindowTitle('Miss Her' if self.role == 'he' else 'Miss Him')

        # 根据角色设置窗口图标
        icon_path = 'assets/icons/miss_her.ico' if self.role == 'he' else 'assets/icons/miss_him.ico'
        self.setWindowIcon(QIcon(icon_path))

        # 设置fluent风格
        apply_stylesheet(self, theme='light_blue.xml' if self.role == 'he' else 'light_pink.xml')

        # 主布局
        layout = QVBoxLayout()

        # 情感状态emoji
        gender_symbol = "♂️" if self.role == 'he' else "♀️"
        self.emotion_status = QLabel(f"{gender_symbol} {self.emotions[self.role]}")
        self.emotion_status.setFont(QFont('Arial', 48))
        layout.addWidget(self.emotion_status)

        # 时间显示
        self.time_label = QLabel("Current Time:")
        layout.addWidget(self.time_label)

        # 互动次数
        self.interaction_count = 0
        self.interaction_count_label = QLabel(f"Interactions: {self.interaction_count}")
        layout.addWidget(self.interaction_count_label)

        # 历史日志
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        layout.addWidget(self.log_text)

        # 控制按钮
        home_button = QPushButton("Home")

        emotion_button = QPushButton("Change Emotion")
        emotion_button.clicked.connect(self.change_emotion)

        there_button = QPushButton("There There")
        there_button.clicked.connect(self.there_there)

        send_pop_button = QPushButton("Send a Pop")
        send_pop_button.clicked.connect(self.send_pop)

        # 添加按钮到布局
        layout.addWidget(home_button)
        layout.addWidget(emotion_button)
        layout.addWidget(there_button)
        layout.addWidget(send_pop_button)

        # 时间更新
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_time)
        self.timer.start(1000)  # 更新频率：1秒

        # 设置中心窗口
        central_widget = QWidget()
        central_widget.setLayout(layout)
        self.setCentralWidget(central_widget)
        self.show()

        # 新建系统托盘图标
        self.tray_icon = QSystemTrayIcon(QIcon(icon_path), self)

        # 创建和连接菜单项
        tray_menu = QMenu()

        home_action = QAction("Home", self)
        # 绑定 home_action 的触发事件到具体函数...

        emotion_action = QAction("Change Emotion", self)
        emotion_action.triggered.connect(self.change_emotion)

        there_action = QAction("There There", self)
        there_action.triggered.connect(self.there_there)

        send_pop_action = QAction("Send a Pop", self)
        send_pop_action.triggered.connect(self.send_pop)

        exit_action = QAction("Exit", self)
        exit_action.triggered.connect(self.close)

        tray_menu.addAction(home_action)
        tray_menu.addAction(emotion_action)
        tray_menu.addAction(there_action)
        tray_menu.addAction(send_pop_action)
        tray_menu.addSeparator()
        tray_menu.addAction(exit_action)

        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.show()


    def init_socket(self):
        self.socket = QTcpSocket(self)

        # 连接信号和槽
        self.socket.errorOccurred.connect(self.socket_error)
        self.socket.connected.connect(self.on_connected)
        self.socket.disconnected.connect(self.on_disconnected)
        self.socket.readyRead.connect(self.on_ready_read)

        self.connect_to_server()

    def connect_to_server(self):
        self.update_status("Attempting to connect to server...")
        self.socket.connectToHost(self.host, self.port)

    def on_connected(self):
        self.update_status("Connected to the server.")

    def on_disconnected(self):
        self.update_status("Disconnected from the server.")

    def on_ready_read(self):
        response = self.socket.readAll().data().decode('utf-8')
        if response:
            # 这里，我们可能需要解析JSON格式的消息，根据消息的类型实行不同的操作
            self.log_text.append(response)
            self.interaction_count += 1
            self.interaction_count_label.setText(f"Interactions: {self.interaction_count}")
        received_data = json.loads(response)
        if received_data.get("type") == "emotion_change":
            emitter_role = received_data["role"]
            # 更新情绪数据
            self.emotions[emitter_role] = received_data["emotion"]
            self.update_emotion_status()  # 根据最新数据更新UI显示
        elif received_data.get("type") == "pop":
            self.show_pop_up(received_data["message"], received_data["role"])
        elif received_data.get("type") == "pop_response":
            # 显示pop_response的弹窗
            self.show_pop_received(received_data["message"])
        elif received_data.get("type") == "there_there":
            # 如果收到了there_there类型的消息，播放音频
            emitter_role = received_data["role"]
            if emitter_role != self.role:
                # 确保消息来自对方
                self.play_random_audio(emitter_role)

    def socket_error(self, socket_error):
        error_message = self.socket.errorString()  # 获取错误描述信息
        logging.error(f"Socket error: {socket_error} - {error_message}")

        if socket_error == QAbstractSocket.ConnectionRefusedError:
            self.update_status("Connection refused by the server.")
        elif socket_error == QAbstractSocket.RemoteHostClosedError:
            self.update_status("Server closed the connection.")
        elif socket_error == QAbstractSocket.HostNotFoundError:
            self.update_status("Server not found.")
        elif socket_error == QAbstractSocket.SocketTimeoutError:
            self.update_status("Connection to the server timed out.")
        else:
            self.update_status(f"Socket error occurred: {socket_error} - {error_message}")

    def update_time(self):
        # 获取当前的时间并格式化
        current_time = QDateTime.currentDateTime().toString('yyyy-MM-dd hh:mm:ss')
        # 更新UI上的时间label
        self.time_label.setText(f"Current Time: {current_time}")

    def update_status(self, message):
        self.log_text.append(message)

    def change_emotion(self):
        print(f"Current role before choosing emotion: {self.role}")  # 调试输出，检查 role 的当前值
        emotions = ["😊", "😔", "😃", "😍", "😢", "😲", "😠"]
        new_emotion, ok = QInputDialog.getItem(self, "Change Emotion",
                                               "Choose your emotion:", emotions, 0, False)
        if ok and new_emotion:
            self.emotions[self.role] = new_emotion
            self.update_emotion_status()  # 更新 UI 上的心情状态
            self.send_message({
                "type": "emotion_change",
                "emotion": new_emotion,
                "role": self.role
            })

    def update_emotion_status(self):
        self.emotion_status.setText(f"♂️ {self.emotions['he']} ❤️ ♀️ {self.emotions['she']}")

    def send_pop(self):
        pop_message, ok = QInputDialog.getText(self, 'Send a Pop', 'Enter your message:')
        if ok and pop_message:
            self.send_message({
                "type": "pop",
                "message": pop_message,
                "role": self.role,
                "target_role": "she" if self.role == "he" else "he"  # 目标角色是相反的
            })
            self.log_text.append(f"Sent Pop: {pop_message}")

    def there_there(self):
        # 用户点击了 There There 按钮，发送消息给对方客户端
        self.send_message({
            "type": "there_there",
            "role": self.role,
            "target_role": "she" if self.role == "he" else "he"
        })

        self.log_text.append("Sent There There.")


    def send_message(self, message):
        print(f"Sending message: {message}")
        if self.socket.state() == QAbstractSocket.ConnectedState:
            data = QByteArray(json.dumps(message).encode('utf-8'))
            self.socket.write(data)
    def show_pop_up(self, message, sender_role):
        # 创建一个消息盒子用于显示 pop message
        pop_msg_box = QMessageBox()
        pop_msg_box.setIcon(QMessageBox.Information)
        pop_msg_box.setText(message)
        pop_msg_box.setWindowTitle(f"A Pop from {'Her' if sender_role == 'he' else 'Him'}!")
        pop_msg_box.setStandardButtons(QMessageBox.Ok)
        pop_msg_box.buttonClicked.connect(self.pop_response)
        pop_msg_box.exec_()

    def pop_response(self, button):
        # 用户点击了消息盒子的按钮，我们可以发送确认消息给对方
        self.send_message(
            {
                "type": "pop_response",
                "message": f"{'He' if self.role == 'he' else 'She'} got it!",
                "role": self.role
            }
        )

    def show_pop_received(self, message):
        QMessageBox.information(self, "Pop Received", message)

    def send_message(self, message):
        # 发送消息到 server
        if self.socket.state() == QAbstractSocket.ConnectedState:
            data = QByteArray(json.dumps(message).encode('utf-8'))
            self.socket.write(data)

    def play_random_audio(self, target_role):
        print(f"Target role is: {target_role}")
        target_folder = os.path.join('assets', 'audios', target_role)  # 根据角色选择文件夹
        # SeeYouTwice/assets/audios/she
        print(target_folder)
        print(os.path.exists(target_folder))
        print(os.path.isdir(target_folder))
        if os.path.exists(target_folder) and os.path.isdir(target_folder):
            files = [f for f in os.listdir(target_folder) if f.endswith('.wav')]
            if files:
                chosen_file = random.choice(files)
                audio_path = os.path.join(target_folder, chosen_file)
                # 使用pygame播放音频
                pygame.mixer.init()
                pygame.mixer.music.load(audio_path)
                pygame.mixer.music.play()
                # while pygame.mixer.music.get_busy():
                #     pygame.time.Clock().tick(10)
def run_client(host, port, role):
    app = QApplication(sys.argv)
    client = Client(host, port, role)
    print(role)
    client.role = role
    print(client.role)
    sys.exit(app.exec_())



if __name__ == '__main__':
    run_client()
