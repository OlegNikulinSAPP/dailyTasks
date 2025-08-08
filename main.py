import wx
import wx.adv
import sqlite3
from datetime import datetime, timedelta
import threading
import time
import webbrowser
import queue


class TaskManagerApp(wx.Frame):
    def __init__(self):
        super().__init__(parent=None, title='Менеджер задач', size=wx.Size(1000, 700))

        # Очередь для межпоточного взаимодействия
        self.reminder_queue = queue.Queue()
        # queue (очередь) представляет собой структуру данных, которая работает по принципу "первым вошел, первым вышел"
        # (FIFO - First In, First Out). Очередь позволяет добавлять элементы в конец очереди и извлекать элементы из
        # начала очереди.
        # Методы класса queue
        # put(item): добавляет элемент item в конец очереди.
        # get(): извлекает и возвращает элемент из начала очереди.
        # empty(): возвращает True, если очередь пуста, и False в противном случае.

        # Инициализация базы данных в главном потоке
        self.init_db()  # вызов метода в этом же классе

        # Создание интерфейса
        self.create_ui()

        # Загрузка данных
        self.load_data()

        # Запуск потока напоминаний
        self.reminder_active = True
        self.reminder_thread = threading.Thread(target=self.check_reminders, daemon=True)
        self.reminder_thread.start()

        # Таймер для проверки очереди напоминаний
        self.timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self.process_reminder_queue, self.timer)
        self.timer.Start(1000)  # Проверка каждую секунду

        # Bind close event to stop reminder thread
        self.Bind(wx.EVT_CLOSE, self.on_close)

        # Set application icon (optional)
        try:
            self.SetIcon(wx.Icon("taskmanager.ico"))
        except:
            pass

    def process_reminder_queue(self, event):
        """Обработка очереди напоминаний в главном потоке"""
        try:
            while not self.reminder_queue.empty():
                reminder = self.reminder_queue.get_nowait()
                self.show_reminder(reminder)
                self.load_reminders()
        except queue.Empty:
            pass

    def init_db(self):
        """Инициализация базы данных и создание таблиц"""
        self.conn = sqlite3.connect('taskmanager.db', check_same_thread=False)
        # Эта строка кода создает подключение к SQLite базе данных с важной настройкой для многопоточности.
        # 1. Основные компоненты:
        # sqlite3.connect() - функция для подключения к SQLite базе
        # 'taskmanager.db' - имя файла базы данных
        # check_same_thread=False - критически важный параметр для многопоточности
        # 2. Что делает параметр check_same_thread=False:
        # Обычное поведение (без параметра): SQLite блокирует использование подключения из других потоков
        # С этим параметром: разрешает использование подключения из разных потоков
        # 3. Почему это важно в вашем приложении:
        # Главный поток: работает с GUI (wxPython)
        # Фоновый поток: проверяет напоминания
        # Оба потока должны иметь доступ к БД

        self.cursor = self.conn.cursor()
        # Эта строка кода создает курсор базы данных - важнейший инструмент для выполнения операций с SQLite.
        # 1. Что такое курсор?
        # Курсор - это объект-посредник, который:
        # Выполняет SQL-запросы (SELECT, INSERT, UPDATE и т.д.)
        # Хранит результаты запросов.
        # Позволяет перемещаться по полученным данным
        # Аналогия: представьте курсор как компьютерную мышь для работы с базой данных.

        # Создание таблиц, если они не существуют
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS work_tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                description TEXT,
                priority INTEGER DEFAULT 2,
                status TEXT DEFAULT 'В ожидании',
                deadline TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                project TEXT,
                assigned_to TEXT,
                category TEXT
            )
        ''')
        # CREATE TABLE - создание новой таблицы
        # IF NOT EXISTS - условное создание (если таблица уже существует, запрос пропускается)
        # work_tasks - имя создаваемой таблицы
        # id - имя поля (первичный ключ), INTEGER - целочисленный тип, PRIMARY KEY - основной уникальный идентификатор,
        # AUTOINCREMENT - автоматическое увеличение значения
        # title - обязательное поле (NOT NULL) для хранения названия задачи
        # description - необязательное поле для подробного описания
        # priority - целое число для приоритета задачи, DEFAULT 2 - значение по умолчанию (средний приоритет)
        # status - Хранит текстовый статус задачи. По умолчанию "В ожидании" (новые задачи)
        # deadline - срок выполнения (хранится как текст в формате ISO)
        # created_at - автоматическая фиксация времени создания (CURRENT_TIMESTAMP)
        # project - название/идентификатор проекта (внешний ключ)
        # assigned_to - идентификатор назначенного сотрудника (исполнитель)
        # category TEXT - произвольная категория для группировки задач

        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS study_tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                description TEXT,
                priority INTEGER DEFAULT 2,
                status TEXT DEFAULT 'В ожидании',
                deadline TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                course TEXT,
                topic TEXT,
                resource_url TEXT
            )
        ''')

        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS personal_goals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                description TEXT,
                priority INTEGER DEFAULT 2,
                status TEXT DEFAULT 'В ожидании',
                deadline TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                category TEXT,
                target_value REAL,
                current_value REAL DEFAULT 0
            )
        ''')

        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS employees (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                position TEXT,
                email TEXT,
                phone TEXT,
                notes TEXT
            )
        ''')

        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS projects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                description TEXT,
                start_date TEXT,
                end_date TEXT,
                status TEXT DEFAULT 'Планирование',
                manager TEXT
            )
        ''')

        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS reminders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                message TEXT NOT NULL,
                remind_time TEXT NOT NULL,
                is_recurring INTEGER DEFAULT 0,
                recurring_interval INTEGER,
                recurring_unit TEXT,
                is_completed INTEGER DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        self.conn.commit()

    def create_ui(self):
        """Создание пользовательского интерфейса"""
        # Создание вкладок
        self.notebook = wx.Notebook(self)

        # Вкладка "Работа"
        self.work_tab = wx.Panel(self.notebook)
        self.create_work_tab()
        self.notebook.AddPage(self.work_tab, "Работа")

        # Вкладка "Учеба"
        self.study_tab = wx.Panel(self.notebook)
        self.create_study_tab()
        self.notebook.AddPage(self.study_tab, "Учеба")

        # Вкладка "Цели"
        self.goals_tab = wx.Panel(self.notebook)
        self.create_goals_tab()
        self.notebook.AddPage(self.goals_tab, "Цели")

        # Вкладка "Напоминания"
        self.reminders_tab = wx.Panel(self.notebook)
        self.create_reminders_tab()
        self.notebook.AddPage(self.reminders_tab, "Напоминания")

        # Строка состояния
        self.status_bar = self.CreateStatusBar(2)
        self.status_bar.SetStatusWidths([-2, -1])
        self.update_status_bar()

        # Главный контейнер
        main_sizer = wx.BoxSizer(wx.VERTICAL)
        main_sizer.Add(self.notebook, 1, wx.EXPAND)
        self.SetSizer(main_sizer)

        # Меню
        self.create_menu_bar()

    def create_menu_bar(self):
        """Создание меню приложения"""
        menu_bar = wx.MenuBar()

        # Меню "Файл"
        file_menu = wx.Menu()
        export_item = file_menu.Append(wx.ID_ANY, "Экспорт данных...")
        import_item = file_menu.Append(wx.ID_ANY, "Импорт данных...")
        file_menu.AppendSeparator()
        exit_item = file_menu.Append(wx.ID_EXIT, "Выход")

        menu_bar.Append(file_menu, "Файл")

        # Меню "Помощь"
        help_menu = wx.Menu()
        about_item = help_menu.Append(wx.ID_ABOUT, "О программе")

        menu_bar.Append(help_menu, "Помощь")

        self.SetMenuBar(menu_bar)

        # Привязка событий
        self.Bind(wx.EVT_MENU, self.on_exit, exit_item)
        self.Bind(wx.EVT_MENU, self.on_about, about_item)
        self.Bind(wx.EVT_MENU, self.on_export, export_item)
        self.Bind(wx.EVT_MENU, self.on_import, import_item)

    def create_work_tab(self):
        """Создание вкладки для работы"""
        panel = self.work_tab

        # Основные элементы
        self.work_task_list = wx.ListCtrl(panel, style=wx.LC_REPORT | wx.BORDER_SUNKEN | wx.LC_SINGLE_SEL)
        self.work_task_list.InsertColumn(0, "ID", width=40)
        self.work_task_list.InsertColumn(1, "Заголовок", width=150)
        self.work_task_list.InsertColumn(2, "Приоритет", width=80)
        self.work_task_list.InsertColumn(3, "Статус", width=100)
        self.work_task_list.InsertColumn(4, "Срок", width=100)
        self.work_task_list.InsertColumn(5, "Проект", width=120)
        self.work_task_list.InsertColumn(6, "Исполнитель", width=120)

        # Кнопки управления
        btn_add = wx.Button(panel, label="Добавить задачу")
        btn_edit = wx.Button(panel, label="Редактировать")
        btn_delete = wx.Button(panel, label="Удалить")
        btn_complete = wx.Button(panel, label="Завершить")

        # Привязка событий
        btn_add.Bind(wx.EVT_BUTTON, self.on_add_work_task)
        btn_edit.Bind(wx.EVT_BUTTON, self.on_edit_work_task)
        btn_delete.Bind(wx.EVT_BUTTON, self.on_delete_work_task)
        btn_complete.Bind(wx.EVT_BUTTON, self.on_complete_work_task)

        # Фильтры
        filter_panel = wx.Panel(panel)
        wx.StaticText(filter_panel, label="Фильтр по статусу:")
        self.work_status_filter = wx.ComboBox(filter_panel, choices=["Все", "В ожидании", "В работе", "Завершено"],
                                              value="Все")
        wx.StaticText(filter_panel, label="Фильтр по проекту:")
        self.work_project_filter = wx.ComboBox(filter_panel)
        self.work_project_filter.Append("Все", None)

        # Заполнение фильтра проектов
        self.cursor.execute("SELECT name FROM projects")
        projects = self.cursor.fetchall()
        for project in projects:
            self.work_project_filter.Append(project[0], project[0])

        # Кнопка применения фильтра
        btn_apply_filter = wx.Button(filter_panel, label="Применить фильтр")
        btn_apply_filter.Bind(wx.EVT_BUTTON, self.on_apply_work_filter)

        # Размещение элементов
        filter_sizer = wx.BoxSizer(wx.HORIZONTAL)
        filter_sizer.Add(wx.StaticText(filter_panel, label="Фильтр по статусу:"), 0, wx.ALIGN_CENTER | wx.RIGHT, 5)
        filter_sizer.Add(self.work_status_filter, 0, wx.EXPAND | wx.RIGHT, 10)
        filter_sizer.Add(wx.StaticText(filter_panel, label="Фильтр по проекту:"), 0, wx.ALIGN_CENTER | wx.RIGHT, 5)
        filter_sizer.Add(self.work_project_filter, 0, wx.EXPAND | wx.RIGHT, 10)
        filter_sizer.Add(btn_apply_filter, 0, wx.EXPAND)
        filter_panel.SetSizer(filter_sizer)

        # Вкладки для работы (задачи, сотрудники, проекты)
        work_notebook = wx.Notebook(panel)

        # Вкладка "Задачи"
        tasks_panel = wx.Panel(work_notebook)
        work_notebook.AddPage(tasks_panel, "Задачи")

        # Вкладка "Сотрудники"
        employees_panel = wx.Panel(work_notebook)
        self.create_employees_tab(employees_panel)
        work_notebook.AddPage(employees_panel, "Сотрудники")

        # Вкладка "Проекты"
        projects_panel = wx.Panel(work_notebook)
        self.create_projects_tab(projects_panel)
        work_notebook.AddPage(projects_panel, "Проекты")

        # Размещение элементов на вкладке "Работа"
        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        btn_sizer.Add(btn_add, 1, wx.EXPAND | wx.RIGHT, 5)
        btn_sizer.Add(btn_edit, 1, wx.EXPAND | wx.RIGHT, 5)
        btn_sizer.Add(btn_delete, 1, wx.EXPAND | wx.RIGHT, 5)
        btn_sizer.Add(btn_complete, 1, wx.EXPAND)

        main_sizer = wx.BoxSizer(wx.VERTICAL)
        main_sizer.Add(filter_panel, 0, wx.EXPAND | wx.ALL, 5)
        main_sizer.Add(work_notebook, 1, wx.EXPAND | wx.ALL, 5)
        main_sizer.Add(self.work_task_list, 1, wx.EXPAND | wx.ALL, 5)
        main_sizer.Add(btn_sizer, 0, wx.EXPAND | wx.ALL, 5)

        panel.SetSizer(main_sizer)

    def create_study_tab(self):
        """Создание вкладки для учебы"""
        panel = self.study_tab

        # Список задач
        self.study_task_list = wx.ListCtrl(panel, style=wx.LC_REPORT | wx.BORDER_SUNKEN | wx.LC_SINGLE_SEL)
        self.study_task_list.InsertColumn(0, "ID", width=40)
        self.study_task_list.InsertColumn(1, "Заголовок", width=200)
        self.study_task_list.InsertColumn(2, "Курс", width=150)
        self.study_task_list.InsertColumn(3, "Тема", width=150)
        self.study_task_list.InsertColumn(4, "Приоритет", width=80)
        self.study_task_list.InsertColumn(5, "Статус", width=100)
        self.study_task_list.InsertColumn(6, "Срок", width=100)

        # Кнопки управления
        btn_add = wx.Button(panel, label="Добавить задачу")
        btn_edit = wx.Button(panel, label="Редактировать")
        btn_delete = wx.Button(panel, label="Удалить")
        btn_complete = wx.Button(panel, label="Завершить")
        btn_open_resource = wx.Button(panel, label="Открыть ресурс")

        # Привязка событий
        btn_add.Bind(wx.EVT_BUTTON, self.on_add_study_task)
        btn_edit.Bind(wx.EVT_BUTTON, self.on_edit_study_task)
        btn_delete.Bind(wx.EVT_BUTTON, self.on_delete_study_task)
        btn_complete.Bind(wx.EVT_BUTTON, self.on_complete_study_task)
        btn_open_resource.Bind(wx.EVT_BUTTON, self.on_open_study_resource)

        # Фильтры
        filter_panel = wx.Panel(panel)
        wx.StaticText(filter_panel, label="Фильтр по курсу:")
        self.study_course_filter = wx.ComboBox(filter_panel)
        self.study_course_filter.Append("Все", None)

        # Заполнение фильтра курсов
        self.cursor.execute("SELECT DISTINCT course FROM study_tasks")
        courses = self.cursor.fetchall()
        for course in courses:
            if course[0]:
                self.study_course_filter.Append(course[0], course[0])

        wx.StaticText(filter_panel, label="Фильтр по статусу:")
        self.study_status_filter = wx.ComboBox(filter_panel, choices=["Все", "В ожидании", "В работе", "Завершено"],
                                               value="Все")

        # Кнопка применения фильтра
        btn_apply_filter = wx.Button(filter_panel, label="Применить фильтр")
        btn_apply_filter.Bind(wx.EVT_BUTTON, self.on_apply_study_filter)

        # Размещение элементов фильтра
        filter_sizer = wx.BoxSizer(wx.HORIZONTAL)
        filter_sizer.Add(wx.StaticText(filter_panel, label="Фильтр по курсу:"), 0, wx.ALIGN_CENTER | wx.RIGHT, 5)
        filter_sizer.Add(self.study_course_filter, 0, wx.EXPAND | wx.RIGHT, 10)
        filter_sizer.Add(wx.StaticText(filter_panel, label="Фильтр по статусу:"), 0, wx.ALIGN_CENTER | wx.RIGHT, 5)
        filter_sizer.Add(self.study_status_filter, 0, wx.EXPAND | wx.RIGHT, 10)
        filter_sizer.Add(btn_apply_filter, 0, wx.EXPAND)
        filter_panel.SetSizer(filter_sizer)

        # Прогресс обучения
        progress_panel = wx.Panel(panel)
        wx.StaticText(progress_panel, label="Прогресс обучения:")
        self.study_progress = wx.Gauge(progress_panel, range=100)

        # Размещение элементов прогресса
        progress_sizer = wx.BoxSizer(wx.HORIZONTAL)
        progress_sizer.Add(wx.StaticText(progress_panel, label="Прогресс обучения:"), 0, wx.ALIGN_CENTER | wx.RIGHT, 5)
        progress_sizer.Add(self.study_progress, 1, wx.EXPAND)
        progress_panel.SetSizer(progress_sizer)

        # Размещение элементов на вкладке
        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        btn_sizer.Add(btn_add, 1, wx.EXPAND | wx.RIGHT, 5)
        btn_sizer.Add(btn_edit, 1, wx.EXPAND | wx.RIGHT, 5)
        btn_sizer.Add(btn_delete, 1, wx.EXPAND | wx.RIGHT, 5)
        btn_sizer.Add(btn_complete, 1, wx.EXPAND | wx.RIGHT, 5)
        btn_sizer.Add(btn_open_resource, 1, wx.EXPAND)

        main_sizer = wx.BoxSizer(wx.VERTICAL)
        main_sizer.Add(filter_panel, 0, wx.EXPAND | wx.ALL, 5)
        main_sizer.Add(progress_panel, 0, wx.EXPAND | wx.ALL, 5)
        main_sizer.Add(self.study_task_list, 1, wx.EXPAND | wx.ALL, 5)
        main_sizer.Add(btn_sizer, 0, wx.EXPAND | wx.ALL, 5)

        panel.SetSizer(main_sizer)

    def create_goals_tab(self):
        """Создание вкладки для личных целей"""
        panel = self.goals_tab

        # Список целей
        self.goals_list = wx.ListCtrl(panel, style=wx.LC_REPORT | wx.BORDER_SUNKEN | wx.LC_SINGLE_SEL)
        self.goals_list.InsertColumn(0, "ID", width=40)
        self.goals_list.InsertColumn(1, "Цель", width=200)
        self.goals_list.InsertColumn(2, "Категория", width=120)
        self.goals_list.InsertColumn(3, "Прогресс", width=120)
        self.goals_list.InsertColumn(4, "Приоритет", width=80)
        self.goals_list.InsertColumn(5, "Статус", width=100)
        self.goals_list.InsertColumn(6, "Срок", width=100)

        # Кнопки управления
        btn_add = wx.Button(panel, label="Добавить цель")
        btn_edit = wx.Button(panel, label="Редактировать")
        btn_delete = wx.Button(panel, label="Удалить")
        btn_complete = wx.Button(panel, label="Завершить")
        btn_update_progress = wx.Button(panel, label="Обновить прогресс")

        # Привязка событий
        btn_add.Bind(wx.EVT_BUTTON, self.on_add_goal)
        btn_edit.Bind(wx.EVT_BUTTON, self.on_edit_goal)
        btn_delete.Bind(wx.EVT_BUTTON, self.on_delete_goal)
        btn_complete.Bind(wx.EVT_BUTTON, self.on_complete_goal)
        btn_update_progress.Bind(wx.EVT_BUTTON, self.on_update_goal_progress)

        # Фильтры
        filter_panel = wx.Panel(panel)
        wx.StaticText(filter_panel, label="Фильтр по категории:")
        self.goal_category_filter = wx.ComboBox(filter_panel)
        self.goal_category_filter.Append("Все", None)

        # Заполнение фильтра категорий
        self.cursor.execute("SELECT DISTINCT category FROM personal_goals")
        categories = self.cursor.fetchall()
        for category in categories:
            if category[0]:
                self.goal_category_filter.Append(category[0], category[0])

        wx.StaticText(filter_panel, label="Фильтр по статусу:")
        self.goal_status_filter = wx.ComboBox(filter_panel, choices=["Все", "В ожидании", "В процессе", "Достигнуто"],
                                              value="Все")

        # Кнопка применения фильтра
        btn_apply_filter = wx.Button(filter_panel, label="Применить фильтр")
        btn_apply_filter.Bind(wx.EVT_BUTTON, self.on_apply_goal_filter)

        # Размещение элементов фильтра
        filter_sizer = wx.BoxSizer(wx.HORIZONTAL)
        filter_sizer.Add(wx.StaticText(filter_panel, label="Фильтр по категории:"), 0, wx.ALIGN_CENTER | wx.RIGHT, 5)
        filter_sizer.Add(self.goal_category_filter, 0, wx.EXPAND | wx.RIGHT, 10)
        filter_sizer.Add(wx.StaticText(filter_panel, label="Фильтр по статусу:"), 0, wx.ALIGN_CENTER | wx.RIGHT, 5)
        filter_sizer.Add(self.goal_status_filter, 0, wx.EXPAND | wx.RIGHT, 10)
        filter_sizer.Add(btn_apply_filter, 0, wx.EXPAND)
        filter_panel.SetSizer(filter_sizer)

        # Общая статистика по целям
        stats_panel = wx.Panel(panel)
        self.goals_stats_text = wx.StaticText(stats_panel, label="Всего целей: 0 | Завершено: 0 (0%)")

        # Размещение статистики
        stats_sizer = wx.BoxSizer(wx.HORIZONTAL)
        stats_sizer.Add(self.goals_stats_text, 0, wx.ALIGN_CENTER)
        stats_panel.SetSizer(stats_sizer)

        # Размещение элементов на вкладке
        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        btn_sizer.Add(btn_add, 1, wx.EXPAND | wx.RIGHT, 5)
        btn_sizer.Add(btn_edit, 1, wx.EXPAND | wx.RIGHT, 5)
        btn_sizer.Add(btn_delete, 1, wx.EXPAND | wx.RIGHT, 5)
        btn_sizer.Add(btn_complete, 1, wx.EXPAND | wx.RIGHT, 5)
        btn_sizer.Add(btn_update_progress, 1, wx.EXPAND)

        main_sizer = wx.BoxSizer(wx.VERTICAL)
        main_sizer.Add(filter_panel, 0, wx.EXPAND | wx.ALL, 5)
        main_sizer.Add(stats_panel, 0, wx.EXPAND | wx.ALL, 5)
        main_sizer.Add(self.goals_list, 1, wx.EXPAND | wx.ALL, 5)
        main_sizer.Add(btn_sizer, 0, wx.EXPAND | wx.ALL, 5)

        panel.SetSizer(main_sizer)

    def create_reminders_tab(self):
        """Создание вкладки для напоминаний"""
        panel = self.reminders_tab

        # Список напоминаний
        self.reminders_list = wx.ListCtrl(panel, style=wx.LC_REPORT | wx.BORDER_SUNKEN | wx.LC_SINGLE_SEL)
        self.reminders_list.InsertColumn(0, "ID", width=40)
        self.reminders_list.InsertColumn(1, "Сообщение", width=300)
        self.reminders_list.InsertColumn(2, "Время напоминания", width=150)
        self.reminders_list.InsertColumn(3, "Повторение", width=100)
        self.reminders_list.InsertColumn(4, "Статус", width=100)

        # Кнопки управления
        btn_add = wx.Button(panel, label="Добавить напоминание")
        btn_edit = wx.Button(panel, label="Редактировать")
        btn_delete = wx.Button(panel, label="Удалить")
        btn_complete = wx.Button(panel, label="Отметить выполненным")

        # Привязка событий
        btn_add.Bind(wx.EVT_BUTTON, self.on_add_reminder)
        btn_edit.Bind(wx.EVT_BUTTON, self.on_edit_reminder)
        btn_delete.Bind(wx.EVT_BUTTON, self.on_delete_reminder)
        btn_complete.Bind(wx.EVT_BUTTON, self.on_complete_reminder)

        # Размещение элементов
        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        btn_sizer.Add(btn_add, 1, wx.EXPAND | wx.RIGHT, 5)
        btn_sizer.Add(btn_edit, 1, wx.EXPAND | wx.RIGHT, 5)
        btn_sizer.Add(btn_delete, 1, wx.EXPAND | wx.RIGHT, 5)
        btn_sizer.Add(btn_complete, 1, wx.EXPAND)

        main_sizer = wx.BoxSizer(wx.VERTICAL)
        main_sizer.Add(self.reminders_list, 1, wx.EXPAND | wx.ALL, 5)
        main_sizer.Add(btn_sizer, 0, wx.EXPAND | wx.ALL, 5)

        panel.SetSizer(main_sizer)

    def create_employees_tab(self, panel):
        """Создание вкладки для сотрудников"""
        # Список сотрудников
        self.employees_list = wx.ListCtrl(panel, style=wx.LC_REPORT | wx.BORDER_SUNKEN | wx.LC_SINGLE_SEL)
        self.employees_list.InsertColumn(0, "ID", width=40)
        self.employees_list.InsertColumn(1, "Имя", width=150)
        self.employees_list.InsertColumn(2, "Должность", width=150)
        self.employees_list.InsertColumn(3, "Email", width=150)
        self.employees_list.InsertColumn(4, "Телефон", width=120)

        # Кнопки управления
        btn_add = wx.Button(panel, label="Добавить сотрудника")
        btn_edit = wx.Button(panel, label="Редактировать")
        btn_delete = wx.Button(panel, label="Удалить")

        # Привязка событий
        btn_add.Bind(wx.EVT_BUTTON, self.on_add_employee)
        btn_edit.Bind(wx.EVT_BUTTON, self.on_edit_employee)
        btn_delete.Bind(wx.EVT_BUTTON, self.on_delete_employee)

        # Размещение элементов
        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        btn_sizer.Add(btn_add, 1, wx.EXPAND | wx.RIGHT, 5)
        btn_sizer.Add(btn_edit, 1, wx.EXPAND | wx.RIGHT, 5)
        btn_sizer.Add(btn_delete, 1, wx.EXPAND)

        main_sizer = wx.BoxSizer(wx.VERTICAL)
        main_sizer.Add(self.employees_list, 1, wx.EXPAND | wx.ALL, 5)
        main_sizer.Add(btn_sizer, 0, wx.EXPAND | wx.ALL, 5)

        panel.SetSizer(main_sizer)

    def create_projects_tab(self, panel):
        """Создание вкладки для проектов"""
        # Список проектов
        self.projects_list = wx.ListCtrl(panel, style=wx.LC_REPORT | wx.BORDER_SUNKEN | wx.LC_SINGLE_SEL)
        self.projects_list.InsertColumn(0, "ID", width=40)
        self.projects_list.InsertColumn(1, "Название", width=200)
        self.projects_list.InsertColumn(2, "Статус", width=100)
        self.projects_list.InsertColumn(3, "Начало", width=100)
        self.projects_list.InsertColumn(4, "Завершение", width=100)
        self.projects_list.InsertColumn(5, "Руководитель", width=150)

        # Кнопки управления
        btn_add = wx.Button(panel, label="Добавить проект")
        btn_edit = wx.Button(panel, label="Редактировать")
        btn_delete = wx.Button(panel, label="Удалить")
        btn_view_tasks = wx.Button(panel, label="Просмотреть задачи")

        # Привязка событий
        btn_add.Bind(wx.EVT_BUTTON, self.on_add_project)
        btn_edit.Bind(wx.EVT_BUTTON, self.on_edit_project)
        btn_delete.Bind(wx.EVT_BUTTON, self.on_delete_project)
        btn_view_tasks.Bind(wx.EVT_BUTTON, self.on_view_project_tasks)

        # Размещение элементов
        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        btn_sizer.Add(btn_add, 1, wx.EXPAND | wx.RIGHT, 5)
        btn_sizer.Add(btn_edit, 1, wx.EXPAND | wx.RIGHT, 5)
        btn_sizer.Add(btn_delete, 1, wx.EXPAND | wx.RIGHT, 5)
        btn_sizer.Add(btn_view_tasks, 1, wx.EXPAND)

        main_sizer = wx.BoxSizer(wx.VERTICAL)
        main_sizer.Add(self.projects_list, 1, wx.EXPAND | wx.ALL, 5)
        main_sizer.Add(btn_sizer, 0, wx.EXPAND | wx.ALL, 5)

        panel.SetSizer(main_sizer)

    def load_data(self):
        """Загрузка данных из базы данных"""
        # Загрузка рабочих задач
        self.load_work_tasks()

        # Загрузка учебных задач
        self.load_study_tasks()

        # Загрузка целей
        self.load_goals()

        # Загрузка сотрудников
        self.load_employees()

        # Загрузка проектов
        self.load_projects()

        # Загрузка напоминаний
        self.load_reminders()

        # Обновление статистики
        self.update_stats()

    def load_work_tasks(self, status_filter=None, project_filter=None):
        """Загрузка рабочих задач"""
        self.work_task_list.DeleteAllItems()

        query = "SELECT * FROM work_tasks"
        params = []

        if status_filter and status_filter != "Все":
            query += " WHERE status = ?"
            params.append(status_filter)

            if project_filter and project_filter != "Все":
                query += " AND project = ?"
                params.append(project_filter)
        elif project_filter and project_filter != "Все":
            query += " WHERE project = ?"
            params.append(project_filter)

        query += " ORDER BY deadline, priority"

        self.cursor.execute(query, params)
        tasks = self.cursor.fetchall()

        for task in tasks:
            idx = self.work_task_list.InsertItem(self.work_task_list.GetItemCount(), str(task[0]))
            self.work_task_list.SetItem(idx, 1, task[1])
            self.work_task_list.SetItem(idx, 2, str(task[3]))
            self.work_task_list.SetItem(idx, 3, task[4])
            self.work_task_list.SetItem(idx, 4, task[5] if task[5] else "")
            self.work_task_list.SetItem(idx, 5, task[7] if task[7] else "")
            self.work_task_list.SetItem(idx, 6, task[8] if task[8] else "")

            # Подсветка просроченных задач
            if task[5] and task[4] != "Завершено":
                deadline = datetime.strptime(task[5], "%Y-%m-%d %H:%M:%S")
                if deadline < datetime.now():
                    self.work_task_list.SetItemTextColour(idx, wx.RED)

    def load_study_tasks(self, course_filter=None, status_filter=None):
        """Загрузка учебных задач"""
        self.study_task_list.DeleteAllItems()

        query = "SELECT * FROM study_tasks"
        params = []

        if course_filter and course_filter != "Все":
            query += " WHERE course = ?"
            params.append(course_filter)

            if status_filter and status_filter != "Все":
                query += " AND status = ?"
                params.append(status_filter)
        elif status_filter and status_filter != "Все":
            query += " WHERE status = ?"
            params.append(status_filter)

        query += " ORDER BY deadline, priority"

        self.cursor.execute(query, params)
        tasks = self.cursor.fetchall()

        for task in tasks:
            idx = self.study_task_list.InsertItem(self.study_task_list.GetItemCount(), str(task[0]))
            self.study_task_list.SetItem(idx, 1, task[1])
            self.study_task_list.SetItem(idx, 2, task[7] if task[7] else "")
            self.study_task_list.SetItem(idx, 3, task[8] if task[8] else "")
            self.study_task_list.SetItem(idx, 4, str(task[3]))
            self.study_task_list.SetItem(idx, 5, task[4])
            self.study_task_list.SetItem(idx, 6, task[5] if task[5] else "")

            # Подсветка просроченных задач
            if task[5] and task[4] != "Завершено":
                deadline = datetime.strptime(task[5], "%Y-%m-%d %H:%M:%S")
                if deadline < datetime.now():
                    self.study_task_list.SetItemTextColour(idx, wx.RED)

    def load_goals(self, category_filter=None, status_filter=None):
        """Загрузка личных целей"""
        self.goals_list.DeleteAllItems()

        query = "SELECT * FROM personal_goals"
        params = []

        if category_filter and category_filter != "Все":
            query += " WHERE category = ?"
            params.append(category_filter)

            if status_filter and status_filter != "Все":
                query += " AND status = ?"
                params.append(status_filter)
        elif status_filter and status_filter != "Все":
            query += " WHERE status = ?"
            params.append(status_filter)

        query += " ORDER BY deadline, priority"

        self.cursor.execute(query, params)
        goals = self.cursor.fetchall()

        for goal in goals:
            idx = self.goals_list.InsertItem(self.goals_list.GetItemCount(), str(goal[0]))
            self.goals_list.SetItem(idx, 1, goal[1])
            self.goals_list.SetItem(idx, 2, goal[7] if goal[7] else "")

            # Расчет прогресса
            if goal[8] and goal[9] is not None:
                progress = f"{goal[9]}/{goal[8]} ({int((goal[9] / goal[8]) * 100)}%)" if goal[8] != 0 else "0/0 (0%)"
                self.goals_list.SetItem(idx, 3, progress)
            else:
                self.goals_list.SetItem(idx, 3, "N/A")

            self.goals_list.SetItem(idx, 4, str(goal[3]))
            self.goals_list.SetItem(idx, 5, goal[4])
            self.goals_list.SetItem(idx, 6, goal[5] if goal[5] else "")

            # Подсветка просроченных целей
            if goal[5] and goal[4] != "Достигнуто":
                deadline = datetime.strptime(goal[5], "%Y-%m-%d %H:%M:%S")
                if deadline < datetime.now():
                    self.goals_list.SetItemTextColour(idx, wx.RED)

    def load_employees(self):
        """Загрузка списка сотрудников"""
        self.employees_list.DeleteAllItems()

        self.cursor.execute("SELECT * FROM employees ORDER BY name")
        employees = self.cursor.fetchall()

        for emp in employees:
            idx = self.employees_list.InsertItem(self.employees_list.GetItemCount(), str(emp[0]))
            self.employees_list.SetItem(idx, 1, emp[1])
            self.employees_list.SetItem(idx, 2, emp[2] if emp[2] else "")
            self.employees_list.SetItem(idx, 3, emp[3] if emp[3] else "")
            self.employees_list.SetItem(idx, 4, emp[4] if emp[4] else "")

    def load_projects(self):
        """Загрузка списка проектов"""
        self.projects_list.DeleteAllItems()

        self.cursor.execute("SELECT * FROM projects ORDER BY end_date, start_date")
        projects = self.cursor.fetchall()

        for proj in projects:
            idx = self.projects_list.InsertItem(self.projects_list.GetItemCount(), str(proj[0]))
            self.projects_list.SetItem(idx, 1, proj[1])
            self.projects_list.SetItem(idx, 2, proj[5])
            self.projects_list.SetItem(idx, 3, proj[3] if proj[3] else "")
            self.projects_list.SetItem(idx, 4, proj[4] if proj[4] else "")
            self.projects_list.SetItem(idx, 5, proj[6] if proj[6] else "")

            # Подсветка просроченных проектов
            if proj[4] and proj[5] != "Завершен":
                end_date = datetime.strptime(proj[4], "%Y-%m-%d %H:%M:%S")
                if end_date < datetime.now():
                    self.projects_list.SetItemTextColour(idx, wx.RED)

    def load_reminders(self):
        """Загрузка напоминаний"""
        self.reminders_list.DeleteAllItems()

        self.cursor.execute("SELECT * FROM reminders WHERE is_completed = 0 ORDER BY remind_time")
        reminders = self.cursor.fetchall()

        for rem in reminders:
            idx = self.reminders_list.InsertItem(self.reminders_list.GetItemCount(), str(rem[0]))
            self.reminders_list.SetItem(idx, 1, rem[1])
            self.reminders_list.SetItem(idx, 2, rem[2])

            if rem[3]:  # is_recurring
                recurring_text = f"Каждые {rem[4]} {rem[5]}"
                self.reminders_list.SetItem(idx, 3, recurring_text)
            else:
                self.reminders_list.SetItem(idx, 3, "Однократно")

            self.reminders_list.SetItem(idx, 4, "Активно")

            # Подсветка просроченных напоминаний
            remind_time = datetime.strptime(rem[2], "%Y-%m-%d %H:%M:%S")
            if remind_time < datetime.now():
                self.reminders_list.SetItemTextColour(idx, wx.RED)

    def update_stats(self):
        """Обновление статистики"""
        # Статистика по рабочим задачам
        self.cursor.execute("SELECT COUNT(*) FROM work_tasks")
        total_work_tasks = self.cursor.fetchone()[0]

        self.cursor.execute("SELECT COUNT(*) FROM work_tasks WHERE status = 'Завершено'")
        completed_work_tasks = self.cursor.fetchone()[0]

        # Статистика по учебным задачам
        self.cursor.execute("SELECT COUNT(*) FROM study_tasks")
        total_study_tasks = self.cursor.fetchone()[0]

        self.cursor.execute("SELECT COUNT(*) FROM study_tasks WHERE status = 'Завершено'")
        completed_study_tasks = self.cursor.fetchone()[0]

        # Статистика по целям
        self.cursor.execute("SELECT COUNT(*) FROM personal_goals")
        total_goals = self.cursor.fetchone()[0]

        self.cursor.execute("SELECT COUNT(*) FROM personal_goals WHERE status = 'Достигнуто'")
        completed_goals = self.cursor.fetchone()[0]

        # Обновление строки состояния
        work_stats = f"Работа: {completed_work_tasks}/{total_work_tasks}"
        study_stats = f"Учеба: {completed_study_tasks}/{total_study_tasks}"
        goals_stats = f"Цели: {completed_goals}/{total_goals}"

        self.status_bar.SetStatusText(f"{work_stats} | {study_stats} | {goals_stats}", 0)

        # Обновление прогресса обучения
        if total_study_tasks > 0:
            progress = int((completed_study_tasks / total_study_tasks) * 100)
            self.study_progress.SetValue(progress)

        # Обновление статистики целей
        if total_goals > 0:
            completion_percent = int((completed_goals / total_goals) * 100)
            self.goals_stats_text.SetLabel(
                f"Всего целей: {total_goals} | Завершено: {completed_goals} ({completion_percent}%)"
            )
        else:
            self.goals_stats_text.SetLabel("Всего целей: 0 | Завершено: 0 (0%)")

    def check_reminders(self):
        """Проверка напоминаний в фоновом режиме"""
        while self.reminder_active:
            try:
                # Создаем новое соединение с БД для этого потока
                conn = sqlite3.connect('taskmanager.db')
                cursor = conn.cursor()

                now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                # Проверка активных напоминаний
                cursor.execute(
                    "SELECT * FROM reminders WHERE is_completed = 0 AND remind_time <= ?",
                    (now,)
                )
                reminders = cursor.fetchall()

                for reminder in reminders:
                    # Помещаем напоминание в очередь для обработки в главном потоке
                    self.reminder_queue.put(reminder)

                    # Обработка повторяющихся напоминаний
                    if reminder[3]:  # is_recurring
                        self.update_recurring_reminder(cursor, reminder)
                    else:
                        # Пометить как выполненное для однократных напоминаний
                        cursor.execute(
                            "UPDATE reminders SET is_completed = 1 WHERE id = ?",
                            (reminder[0],)
                        )
                        conn.commit()

                conn.close()

                # Проверка каждую минуту
                time.sleep(60)

            except Exception as e:
                print(f"Ошибка в потоке напоминаний: {e}")
                time.sleep(10)  # Подождать перед следующей попыткой

    def show_reminder(self, reminder):
        """Показ всплывающего напоминания"""
        dlg = wx.MessageDialog(
            self,
            reminder[1],  # message
            "Напоминание",
            wx.OK | wx.ICON_INFORMATION
        )
        dlg.ShowModal()
        dlg.Destroy()

    def update_recurring_reminder(self, cursor, reminder):
        """Обновление времени для повторяющегося напоминания"""
        remind_time = datetime.strptime(reminder[2], "%Y-%m-%d %H:%M:%S")
        interval = reminder[4]
        unit = reminder[5]

        if unit == "minutes":
            new_time = remind_time + timedelta(minutes=interval)
        elif unit == "hours":
            new_time = remind_time + timedelta(hours=interval)
        elif unit == "days":
            new_time = remind_time + timedelta(days=interval)
        elif unit == "weeks":
            new_time = remind_time + timedelta(weeks=interval)
        elif unit == "months":
            # Приблизительно, так как months в timedelta нет
            new_time = remind_time.replace(
                year=remind_time.year + (remind_time.month + interval - 1) // 12,
                month=(remind_time.month + interval - 1) % 12 + 1
            )
        else:
            return

        cursor.execute(
            "UPDATE reminders SET remind_time = ? WHERE id = ?",
            (new_time.strftime("%Y-%m-%d %H:%M:%S"), reminder[0])
        )

    # Обработчики событий для вкладки "Работа"
    def on_add_work_task(self, event):
        """Добавление новой рабочей задачи"""
        dlg = WorkTaskDialog(self, title="Добавить рабочую задачу")
        if dlg.ShowModal() == wx.ID_OK:
            task_data = dlg.get_data()

            self.cursor.execute(
                '''INSERT INTO work_tasks 
                (title, description, priority, status, deadline, project, assigned_to, category)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
                task_data
            )
            self.conn.commit()
            self.load_work_tasks()
            self.update_stats()

        dlg.Destroy()

    def on_edit_work_task(self, event):
        """Редактирование рабочей задачи"""
        selected = self.work_task_list.GetFirstSelected()
        if selected == -1:
            wx.MessageBox("Выберите задачу для редактирования", "Ошибка", wx.OK | wx.ICON_WARNING)
            return

        task_id = int(self.work_task_list.GetItemText(selected))
        self.cursor.execute("SELECT * FROM work_tasks WHERE id = ?", (task_id,))
        task_data = self.cursor.fetchone()

        dlg = WorkTaskDialog(self, title="Редактировать рабочую задачу")
        dlg.set_data(task_data)

        if dlg.ShowModal() == wx.ID_OK:
            updated_data = dlg.get_data()

            self.cursor.execute(
                '''UPDATE work_tasks 
                SET title = ?, description = ?, priority = ?, status = ?, 
                    deadline = ?, project = ?, assigned_to = ?, category = ?
                WHERE id = ?''',
                (*updated_data, task_id)
            )
            self.conn.commit()
            self.load_work_tasks()
            self.update_stats()

        dlg.Destroy()

    def on_delete_work_task(self, event):
        """Удаление рабочей задачи"""
        selected = self.work_task_list.GetFirstSelected()
        if selected == -1:
            wx.MessageBox("Выберите задачу для удаления", "Ошибка", wx.OK | wx.ICON_WARNING)
            return

        task_id = int(self.work_task_list.GetItemText(selected))

        confirm = wx.MessageBox(
            "Вы уверены, что хотите удалить эту задачу?",
            "Подтверждение удаления",
            wx.YES_NO | wx.ICON_QUESTION
        )

        if confirm == wx.YES:
            self.cursor.execute("DELETE FROM work_tasks WHERE id = ?", (task_id,))
            self.conn.commit()
            self.load_work_tasks()
            self.update_stats()

    def on_complete_work_task(self, event):
        """Пометить рабочую задачу как завершенную"""
        selected = self.work_task_list.GetFirstSelected()
        if selected == -1:
            wx.MessageBox("Выберите задачу для завершения", "Ошибка", wx.OK | wx.ICON_WARNING)
            return

        task_id = int(self.work_task_list.GetItemText(selected))

        self.cursor.execute(
            "UPDATE work_tasks SET status = 'Завершено' WHERE id = ?",
            (task_id,)
        )
        self.conn.commit()
        self.load_work_tasks()
        self.update_stats()

    def on_apply_work_filter(self, event):
        """Применение фильтров для рабочих задач"""
        status_filter = self.work_status_filter.GetValue()
        project_filter = self.work_project_filter.GetValue()

        self.load_work_tasks(status_filter, project_filter)

    # Обработчики событий для вкладки "Учеба"
    def on_add_study_task(self, event):
        """Добавление новой учебной задачи"""
        dlg = StudyTaskDialog(self, title="Добавить учебную задачу")
        if dlg.ShowModal() == wx.ID_OK:
            task_data = dlg.get_data()

            self.cursor.execute(
                '''INSERT INTO study_tasks 
                (title, description, priority, status, deadline, course, topic, resource_url)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
                task_data
            )
            self.conn.commit()
            self.load_study_tasks()
            self.update_stats()

        dlg.Destroy()

    def on_edit_study_task(self, event):
        """Редактирование учебной задачи"""
        selected = self.study_task_list.GetFirstSelected()
        if selected == -1:
            wx.MessageBox("Выберите задачу для редактирования", "Ошибка", wx.OK | wx.ICON_WARNING)
            return

        task_id = int(self.study_task_list.GetItemText(selected))
        self.cursor.execute("SELECT * FROM study_tasks WHERE id = ?", (task_id,))
        task_data = self.cursor.fetchone()

        dlg = StudyTaskDialog(self, title="Редактировать учебную задачу")
        dlg.set_data(task_data)

        if dlg.ShowModal() == wx.ID_OK:
            updated_data = dlg.get_data()

            self.cursor.execute(
                '''UPDATE study_tasks 
                SET title = ?, description = ?, priority = ?, status = ?, 
                    deadline = ?, course = ?, topic = ?, resource_url = ?
                WHERE id = ?''',
                (*updated_data, task_id)
            )
            self.conn.commit()
            self.load_study_tasks()
            self.update_stats()

        dlg.Destroy()

    def on_delete_study_task(self, event):
        """Удаление учебной задачи"""
        selected = self.study_task_list.GetFirstSelected()
        if selected == -1:
            wx.MessageBox("Выберите задачу для удаления", "Ошибка", wx.OK | wx.ICON_WARNING)
            return

        task_id = int(self.study_task_list.GetItemText(selected))

        confirm = wx.MessageBox(
            "Вы уверены, что хотите удалить эту задачу?",
            "Подтверждение удаления",
            wx.YES_NO | wx.ICON_QUESTION
        )

        if confirm == wx.YES:
            self.cursor.execute("DELETE FROM study_tasks WHERE id = ?", (task_id,))
            self.conn.commit()
            self.load_study_tasks()
            self.update_stats()

    def on_complete_study_task(self, event):
        """Пометить учебную задачу как завершенную"""
        selected = self.study_task_list.GetFirstSelected()
        if selected == -1:
            wx.MessageBox("Выберите задачу для завершения", "Ошибка", wx.OK | wx.ICON_WARNING)
            return

        task_id = int(self.study_task_list.GetItemText(selected))

        self.cursor.execute(
            "UPDATE study_tasks SET status = 'Завершено' WHERE id = ?",
            (task_id,)
        )
        self.conn.commit()
        self.load_study_tasks()
        self.update_stats()

    def on_open_study_resource(self, event):
        """Открытие учебного ресурса"""
        selected = self.study_task_list.GetFirstSelected()
        if selected == -1:
            wx.MessageBox("Выберите задачу с ресурсом", "Ошибка", wx.OK | wx.ICON_WARNING)
            return

        task_id = int(self.study_task_list.GetItemText(selected))
        self.cursor.execute("SELECT resource_url FROM study_tasks WHERE id = ?", (task_id,))
        url = self.cursor.fetchone()[0]

        if url:
            webbrowser.open(url)
        else:
            wx.MessageBox("Для этой задачи не указан ресурс", "Информация", wx.OK | wx.ICON_INFORMATION)

    def on_apply_study_filter(self, event):
        """Применение фильтров для учебных задач"""
        course_filter = self.study_course_filter.GetValue()
        status_filter = self.study_status_filter.GetValue()

        self.load_study_tasks(course_filter, status_filter)

    # Обработчики событий для вкладки "Цели"
    def on_add_goal(self, event):
        """Добавление новой цели"""
        dlg = GoalDialog(self, title="Добавить цель")
        if dlg.ShowModal() == wx.ID_OK:
            goal_data = dlg.get_data()

            self.cursor.execute(
                '''INSERT INTO personal_goals 
                (title, description, priority, status, deadline, category, target_value, current_value)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
                goal_data
            )
            self.conn.commit()
            self.load_goals()
            self.update_stats()

        dlg.Destroy()

    def on_edit_goal(self, event):
        """Редактирование цели"""
        selected = self.goals_list.GetFirstSelected()
        if selected == -1:
            wx.MessageBox("Выберите цель для редактирования", "Ошибка", wx.OK | wx.ICON_WARNING)
            return

        goal_id = int(self.goals_list.GetItemText(selected))
        self.cursor.execute("SELECT * FROM personal_goals WHERE id = ?", (goal_id,))
        goal_data = self.cursor.fetchone()

        dlg = GoalDialog(self, title="Редактировать цель")
        dlg.set_data(goal_data)

        if dlg.ShowModal() == wx.ID_OK:
            updated_data = dlg.get_data()

            self.cursor.execute(
                '''UPDATE personal_goals 
                SET title = ?, description = ?, priority = ?, status = ?, 
                    deadline = ?, category = ?, target_value = ?, current_value = ?
                WHERE id = ?''',
                (*updated_data, goal_id)
            )
            self.conn.commit()
            self.load_goals()
            self.update_stats()

        dlg.Destroy()

    def on_delete_goal(self, event):
        """Удаление цели"""
        selected = self.goals_list.GetFirstSelected()
        if selected == -1:
            wx.MessageBox("Выберите цель для удаления", "Ошибка", wx.OK | wx.ICON_WARNING)
            return

        goal_id = int(self.goals_list.GetItemText(selected))

        confirm = wx.MessageBox(
            "Вы уверены, что хотите удалить эту цель?",
            "Подтверждение удаления",
            wx.YES_NO | wx.ICON_QUESTION
        )

        if confirm == wx.YES:
            self.cursor.execute("DELETE FROM personal_goals WHERE id = ?", (goal_id,))
            self.conn.commit()
            self.load_goals()
            self.update_stats()

    def on_complete_goal(self, event):
        """Пометить цель как достигнутую"""
        selected = self.goals_list.GetFirstSelected()
        if selected == -1:
            wx.MessageBox("Выберите цель для завершения", "Ошибка", wx.OK | wx.ICON_WARNING)
            return

        goal_id = int(self.goals_list.GetItemText(selected))

        self.cursor.execute(
            "UPDATE personal_goals SET status = 'Достигнуто' WHERE id = ?",
            (goal_id,)
        )
        self.conn.commit()
        self.load_goals()
        self.update_stats()

    def on_update_goal_progress(self, event):
        """Обновление прогресса цели"""
        selected = self.goals_list.GetFirstSelected()
        if selected == -1:
            wx.MessageBox("Выберите цель для обновления прогресса", "Ошибка", wx.OK | wx.ICON_WARNING)
            return

        goal_id = int(self.goals_list.GetItemText(selected))
        self.cursor.execute("SELECT target_value, current_value FROM personal_goals WHERE id = ?", (goal_id,))
        target, current = self.cursor.fetchone()

        if target is None:
            wx.MessageBox("Для этой цели не установлен целевой показатель", "Ошибка", wx.OK | wx.ICON_WARNING)
            return

        dlg = wx.TextEntryDialog(
            self,
            f"Текущее значение (цель: {target}):",
            "Обновить прогресс",
            str(current) if current is not None else ""
        )

        if dlg.ShowModal() == wx.ID_OK:
            try:
                new_value = float(dlg.GetValue())

                self.cursor.execute(
                    "UPDATE personal_goals SET current_value = ? WHERE id = ?",
                    (new_value, goal_id)
                )
                self.conn.commit()

                # Автоматически завершить цель, если достигнут целевой показатель
                if new_value >= target:
                    self.cursor.execute(
                        "UPDATE personal_goals SET status = 'Достигнуто' WHERE id = ?",
                        (goal_id,)
                    )
                    self.conn.commit()

                self.load_goals()
                self.update_stats()
            except ValueError:
                wx.MessageBox("Введите числовое значение", "Ошибка", wx.OK | wx.ICON_ERROR)

        dlg.Destroy()

    def on_apply_goal_filter(self, event):
        """Применение фильтров для целей"""
        category_filter = self.goal_category_filter.GetValue()
        status_filter = self.goal_status_filter.GetValue()

        self.load_goals(category_filter, status_filter)

    # Обработчики событий для вкладки "Напоминания"
    def on_add_reminder(self, event):
        """Добавление нового напоминания"""
        dlg = ReminderDialog(self, title="Добавить напоминание")
        if dlg.ShowModal() == wx.ID_OK:
            reminder_data = dlg.get_data()

            self.cursor.execute(
                '''INSERT INTO reminders 
                (message, remind_time, is_recurring, recurring_interval, recurring_unit)
                VALUES (?, ?, ?, ?, ?)''',
                reminder_data
            )
            self.conn.commit()
            self.load_reminders()

        dlg.Destroy()

    def on_edit_reminder(self, event):
        """Редактирование напоминания"""
        selected = self.reminders_list.GetFirstSelected()
        if selected == -1:
            wx.MessageBox("Выберите напоминание для редактирования", "Ошибка", wx.OK | wx.ICON_WARNING)
            return

        reminder_id = int(self.reminders_list.GetItemText(selected))
        self.cursor.execute("SELECT * FROM reminders WHERE id = ?", (reminder_id,))
        reminder_data = self.cursor.fetchone()

        dlg = ReminderDialog(self, title="Редактировать напоминание")
        dlg.set_data(reminder_data)

        if dlg.ShowModal() == wx.ID_OK:
            updated_data = dlg.get_data()

            self.cursor.execute(
                '''UPDATE reminders 
                SET message = ?, remind_time = ?, is_recurring = ?, 
                    recurring_interval = ?, recurring_unit = ?
                WHERE id = ?''',
                (*updated_data, reminder_id)
            )
            self.conn.commit()
            self.load_reminders()

        dlg.Destroy()

    def on_delete_reminder(self, event):
        """Удаление напоминания"""
        selected = self.reminders_list.GetFirstSelected()
        if selected == -1:
            wx.MessageBox("Выберите напоминание для удаления", "Ошибка", wx.OK | wx.ICON_WARNING)
            return

        reminder_id = int(self.reminders_list.GetItemText(selected))

        confirm = wx.MessageBox(
            "Вы уверены, что хотите удалить это напоминание?",
            "Подтверждение удаления",
            wx.YES_NO | wx.ICON_QUESTION
        )

        if confirm == wx.YES:
            self.cursor.execute("DELETE FROM reminders WHERE id = ?", (reminder_id,))
            self.conn.commit()
            self.load_reminders()

    def on_complete_reminder(self, event):
        """Пометить напоминание как выполненное"""
        selected = self.reminders_list.GetFirstSelected()
        if selected == -1:
            wx.MessageBox("Выберите напоминание для отметки", "Ошибка", wx.OK | wx.ICON_WARNING)
            return

        reminder_id = int(self.reminders_list.GetItemText(selected))

        self.cursor.execute(
            "UPDATE reminders SET is_completed = 1 WHERE id = ?",
            (reminder_id,)
        )
        self.conn.commit()
        self.load_reminders()

    # Обработчики событий для сотрудников
    def on_add_employee(self, event):
        """Добавление нового сотрудника"""
        dlg = EmployeeDialog(self, title="Добавить сотрудника")
        if dlg.ShowModal() == wx.ID_OK:
            employee_data = dlg.get_data()

            self.cursor.execute(
                '''INSERT INTO employees 
                (name, position, email, phone, notes)
                VALUES (?, ?, ?, ?, ?)''',
                employee_data
            )
            self.conn.commit()
            self.load_employees()

        dlg.Destroy()

    def on_edit_employee(self, event):
        """Редактирование сотрудника"""
        selected = self.employees_list.GetFirstSelected()
        if selected == -1:
            wx.MessageBox("Выберите сотрудника для редактирования", "Ошибка", wx.OK | wx.ICON_WARNING)
            return

        employee_id = int(self.employees_list.GetItemText(selected))
        self.cursor.execute("SELECT * FROM employees WHERE id = ?", (employee_id,))
        employee_data = self.cursor.fetchone()

        dlg = EmployeeDialog(self, title="Редактировать сотрудника")
        dlg.set_data(employee_data)

        if dlg.ShowModal() == wx.ID_OK:
            updated_data = dlg.get_data()

            self.cursor.execute(
                '''UPDATE employees 
                SET name = ?, position = ?, email = ?, phone = ?, notes = ?
                WHERE id = ?''',
                (*updated_data, employee_id)
            )
            self.conn.commit()
            self.load_employees()

        dlg.Destroy()

    def on_delete_employee(self, event):
        """Удаление сотрудника"""
        selected = self.employees_list.GetFirstSelected()
        if selected == -1:
            wx.MessageBox("Выберите сотрудника для удаления", "Ошибка", wx.OK | wx.ICON_WARNING)
            return

        employee_id = int(self.employees_list.GetItemText(selected))

        # Проверить, есть ли задачи, связанные с этим сотрудником
        self.cursor.execute("SELECT COUNT(*) FROM work_tasks WHERE assigned_to = ?", (employee_id,))
        task_count = self.cursor.fetchone()[0]

        if task_count > 0:
            wx.MessageBox(
                "Нельзя удалить сотрудника, так как ему назначены задачи. Сначала переназначьте или удалите эти задачи.",
                "Ошибка",
                wx.OK | wx.ICON_ERROR
            )
            return

        confirm = wx.MessageBox(
            "Вы уверены, что хотите удалить этого сотрудника?",
            "Подтверждение удаления",
            wx.YES_NO | wx.ICON_QUESTION
        )

        if confirm == wx.YES:
            self.cursor.execute("DELETE FROM employees WHERE id = ?", (employee_id,))
            self.conn.commit()
            self.load_employees()

    # Обработчики событий для проектов
    def on_add_project(self, event):
        """Добавление нового проекта"""
        dlg = ProjectDialog(self, title="Добавить проект")
        if dlg.ShowModal() == wx.ID_OK:
            project_data = dlg.get_data()

            self.cursor.execute(
                '''INSERT INTO projects 
                (name, description, start_date, end_date, status, manager)
                VALUES (?, ?, ?, ?, ?, ?)''',
                project_data
            )
            self.conn.commit()
            self.load_projects()

        dlg.Destroy()

    def on_edit_project(self, event):
        """Редактирование проекта"""
        selected = self.projects_list.GetFirstSelected()
        if selected == -1:
            wx.MessageBox("Выберите проект для редактирования", "Ошибка", wx.OK | wx.ICON_WARNING)
            return

        project_id = int(self.projects_list.GetItemText(selected))
        self.cursor.execute("SELECT * FROM projects WHERE id = ?", (project_id,))
        project_data = self.cursor.fetchone()

        dlg = ProjectDialog(self, title="Редактировать проект")
        dlg.set_data(project_data)

        if dlg.ShowModal() == wx.ID_OK:
            updated_data = dlg.get_data()

            self.cursor.execute(
                '''UPDATE projects 
                SET name = ?, description = ?, start_date = ?, end_date = ?, status = ?, manager = ?
                WHERE id = ?''',
                (*updated_data, project_id)
            )
            self.conn.commit()
            self.load_projects()

        dlg.Destroy()

    def on_delete_project(self, event):
        """Удаление проекта"""
        selected = self.projects_list.GetFirstSelected()
        if selected == -1:
            wx.MessageBox("Выберите проект для удаления", "Ошибка", wx.OK | wx.ICON_WARNING)
            return

        project_id = int(self.projects_list.GetItemText(selected))

        # Проверить, есть ли задачи, связанные с этим проектом
        self.cursor.execute("SELECT COUNT(*) FROM work_tasks WHERE project = ?", (project_id,))
        task_count = self.cursor.fetchone()[0]

        if task_count > 0:
            wx.MessageBox(
                "Нельзя удалить проект, так как с ним связаны задачи. Сначала удалите или переназначьте эти задачи.",
                "Ошибка",
                wx.OK | wx.ICON_ERROR
            )
            return

        confirm = wx.MessageBox(
            "Вы уверены, что хотите удалить этот проект?",
            "Подтверждение удаления",
            wx.YES_NO | wx.ICON_QUESTION
        )

        if confirm == wx.YES:
            self.cursor.execute("DELETE FROM projects WHERE id = ?", (project_id,))
            self.conn.commit()
            self.load_projects()

    def on_view_project_tasks(self, event):
        """Просмотр задач проекта"""
        selected = self.projects_list.GetFirstSelected()
        if selected == -1:
            wx.MessageBox("Выберите проект для просмотра задач", "Ошибка", wx.OK | wx.ICON_WARNING)
            return

        project_id = int(self.projects_list.GetItemText(selected))
        self.cursor.execute("SELECT name FROM projects WHERE id = ?", (project_id,))
        project_name = self.cursor.fetchone()[0]

        self.cursor.execute(
            "SELECT * FROM work_tasks WHERE project = ? ORDER BY deadline",
            (project_id,)
        )
        tasks = self.cursor.fetchall()

        dlg = wx.Dialog(self, title=f"Задачи проекта: {project_name}")

        task_list = wx.ListCtrl(dlg, style=wx.LC_REPORT | wx.BORDER_SUNKEN | wx.LC_SINGLE_SEL)
        task_list.InsertColumn(0, "ID", width=40)
        task_list.InsertColumn(1, "Заголовок", width=200)
        task_list.InsertColumn(2, "Статус", width=100)
        task_list.InsertColumn(3, "Срок", width=100)
        task_list.InsertColumn(4, "Исполнитель", width=150)

        for task in tasks:
            idx = task_list.InsertItem(task_list.GetItemCount(), str(task[0]))
            task_list.SetItem(idx, 1, task[1])
            task_list.SetItem(idx, 2, task[4])
            task_list.SetItem(idx, 3, task[5] if task[5] else "")

            if task[8]:  # assigned_to
                self.cursor.execute("SELECT name FROM employees WHERE id = ?", (task[8],))
                emp_name = self.cursor.fetchone()
                if emp_name:
                    task_list.SetItem(idx, 4, emp_name[0])

        btn_close = wx.Button(dlg, wx.ID_CLOSE)
        btn_close.Bind(wx.EVT_BUTTON, lambda e: dlg.EndModal(wx.ID_CLOSE))

        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(task_list, 1, wx.EXPAND | wx.ALL, 5)
        sizer.Add(btn_close, 0, wx.ALIGN_CENTER | wx.ALL, 5)

        dlg.SetSizer(sizer)
        dlg.SetSize((600, 400))
        dlg.ShowModal()

    # Обработчики событий меню
    def on_exit(self, event):
        """Закрытие приложения"""
        self.Close()

    def on_about(self, event):
        """Показ информации о программе"""
        info = wx.adv.AboutDialogInfo()
        info.SetName("Менеджер задач")
        info.SetVersion("1.0")
        info.SetDescription("Приложение для управления рабочими, учебными задачами и личными целями")
        info.SetCopyright("(C) 2023")
        info.SetDevelopers(["Ваше имя"])

        wx.adv.AboutBox(info)

    def on_export(self, event):
        """Экспорт данных"""
        # Реализация экспорта данных
        wx.MessageBox("Функция экспорта данных будет реализована в будущей версии", "Информация",
                      wx.OK | wx.ICON_INFORMATION)

    def on_import(self, event):
        """Импорт данных"""
        # Реализация импорта данных
        wx.MessageBox("Функция импорта данных будет реализована в будущей версии", "Информация",
                      wx.OK | wx.ICON_INFORMATION)

    def on_close(self, event):
        """Обработка закрытия окна"""
        self.reminder_active = False
        if self.reminder_thread.is_alive():
            self.reminder_thread.join(timeout=1)

        self.timer.Stop()
        self.conn.close()
        self.Destroy()

    def update_status_bar(self):
        """Обновление строки состояния"""
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.status_bar.SetStatusText(now, 1)


# Диалоговые окна для добавления/редактирования данных
class WorkTaskDialog(wx.Dialog):
    def __init__(self, parent, title):
        super().__init__(parent, title=title, size=(500, 400))

        self.parent = parent

        # Элементы формы
        wx.StaticText(self, label="Заголовок:", pos=(10, 10))
        self.title = wx.TextCtrl(self, pos=(120, 10), size=(350, -1))

        wx.StaticText(self, label="Описание:", pos=(10, 40))
        self.description = wx.TextCtrl(self, pos=(120, 40), size=(350, 100), style=wx.TE_MULTILINE)

        wx.StaticText(self, label="Приоритет:", pos=(10, 150))
        self.priority = wx.SpinCtrl(self, pos=(120, 150), size=(50, -1), min=1, max=5)

        wx.StaticText(self, label="Статус:", pos=(10, 180))
        self.status = wx.ComboBox(self, pos=(120, 180), size=(150, -1),
                                  choices=["В ожидании", "В работе", "Завершено"])

        wx.StaticText(self, label="Срок:", pos=(10, 210))
        self.deadline = wx.adv.DatePickerCtrl(self, pos=(120, 210), style=wx.adv.DP_DROPDOWN | wx.adv.DP_SHOWCENTURY)
        self.time = wx.SpinCtrl(self, pos=(280, 210), size=(50, -1), min=0, max=23)
        wx.StaticText(self, label=":", pos=(335, 210))
        self.minutes = wx.SpinCtrl(self, pos=(345, 210), size=(50, -1), min=0, max=59)

        wx.StaticText(self, label="Проект:", pos=(10, 240))
        self.project = wx.ComboBox(self, pos=(120, 240), size=(150, -1))

        # Заполнение списка проектов
        self.parent.cursor.execute("SELECT id, name FROM projects")
        projects = self.parent.cursor.fetchall()
        self.project.Append("", None)  # Пустой элемент
        for proj_id, proj_name in projects:
            self.project.Append(proj_name, proj_id)

        wx.StaticText(self, label="Исполнитель:", pos=(10, 270))
        self.assigned_to = wx.ComboBox(self, pos=(120, 270), size=(150, -1))

        # Заполнение списка сотрудников
        self.parent.cursor.execute("SELECT id, name FROM employees")
        employees = self.parent.cursor.fetchall()
        self.assigned_to.Append("", None)  # Пустой элемент
        for emp_id, emp_name in employees:
            self.assigned_to.Append(emp_name, emp_id)

        wx.StaticText(self, label="Категория:", pos=(10, 300))
        self.category = wx.TextCtrl(self, pos=(120, 300), size=(150, -1))

        # Кнопки
        btn_ok = wx.Button(self, wx.ID_OK, label="OK", pos=(300, 330))
        btn_cancel = wx.Button(self, wx.ID_CANCEL, label="Отмена", pos=(400, 330))

    def set_data(self, data):
        """Заполнение формы данными"""
        self.title.SetValue(data[1])
        self.description.SetValue(data[2] if data[2] else "")
        self.priority.SetValue(data[3])
        self.status.SetValue(data[4])

        if data[5]:
            deadline = datetime.strptime(data[5], "%Y-%m-%d %H:%M:%S")
            self.deadline.SetValue(wx.DateTime.FromDMY(
                deadline.day, deadline.month - 1, deadline.year
            ))
            self.time.SetValue(deadline.hour)
            self.minutes.SetValue(deadline.minute)

        if data[7]:  # project
            for i in range(self.project.GetCount()):
                if self.project.GetClientData(i) == data[7]:
                    self.project.SetSelection(i)
                    break

        if data[8]:  # assigned_to
            for i in range(self.assigned_to.GetCount()):
                if self.assigned_to.GetClientData(i) == data[8]:
                    self.assigned_to.SetSelection(i)
                    break

        self.category.SetValue(data[9] if data[9] else "")

    def get_data(self):
        """Получение данных из формы"""
        title = self.title.GetValue()
        description = self.description.GetValue()
        priority = self.priority.GetValue()
        status = self.status.GetValue()

        date = self.deadline.GetValue()
        hour = self.time.GetValue()
        minute = self.minutes.GetValue()

        if date.IsValid():
            deadline = f"{date.GetYear()}-{date.GetMonth() + 1:02d}-{date.GetDay():02d} {hour:02d}:{minute:02d}:00"
        else:
            deadline = None

        # Безопасное получение данных проекта
        project_idx = self.project.GetSelection()
        project = self.project.GetClientData(project_idx) if project_idx != wx.NOT_FOUND else None

        # Безопасное получение данных исполнителя
        assigned_idx = self.assigned_to.GetSelection()
        assigned_to = self.assigned_to.GetClientData(assigned_idx) if assigned_idx != wx.NOT_FOUND else None

        category = self.category.GetValue()

        return (
            title, description, priority, status, deadline,
            project, assigned_to, category
        )


class StudyTaskDialog(wx.Dialog):
    def __init__(self, parent, title):
        super().__init__(parent, title=title, size=(500, 400))

        self.parent = parent

        # Элементы формы
        wx.StaticText(self, label="Заголовок:", pos=(10, 10))
        self.title = wx.TextCtrl(self, pos=(120, 10), size=(350, -1))

        wx.StaticText(self, label="Описание:", pos=(10, 40))
        self.description = wx.TextCtrl(self, pos=(120, 40), size=(350, 100), style=wx.TE_MULTILINE)

        wx.StaticText(self, label="Приоритет:", pos=(10, 150))
        self.priority = wx.SpinCtrl(self, pos=(120, 150), size=(50, -1), min=1, max=5)

        wx.StaticText(self, label="Статус:", pos=(10, 180))
        self.status = wx.ComboBox(self, pos=(120, 180), size=(150, -1),
                                  choices=["В ожидании", "В работе", "Завершено"])

        wx.StaticText(self, label="Срок:", pos=(10, 210))
        self.deadline = wx.adv.DatePickerCtrl(self, pos=(120, 210), style=wx.adv.DP_DROPDOWN | wx.adv.DP_SHOWCENTURY)
        self.time = wx.SpinCtrl(self, pos=(280, 210), size=(50, -1), min=0, max=23)
        wx.StaticText(self, label=":", pos=(335, 210))
        self.minutes = wx.SpinCtrl(self, pos=(345, 210), size=(50, -1), min=0, max=59)

        wx.StaticText(self, label="Курс:", pos=(10, 240))
        self.course = wx.TextCtrl(self, pos=(120, 240), size=(350, -1))

        wx.StaticText(self, label="Тема:", pos=(10, 270))
        self.topic = wx.TextCtrl(self, pos=(120, 270), size=(350, -1))

        wx.StaticText(self, label="URL ресурса:", pos=(10, 300))
        self.resource_url = wx.TextCtrl(self, pos=(120, 300), size=(350, -1))

        # Кнопки
        btn_ok = wx.Button(self, wx.ID_OK, label="OK", pos=(300, 330))
        btn_cancel = wx.Button(self, wx.ID_CANCEL, label="Отмена", pos=(400, 330))

    def set_data(self, data):
        """Заполнение формы данными"""
        self.title.SetValue(data[1])
        self.description.SetValue(data[2] if data[2] else "")
        self.priority.SetValue(data[3])
        self.status.SetValue(data[4])

        if data[5]:
            deadline = datetime.strptime(data[5], "%Y-%m-%d %H:%M:%S")
            self.deadline.SetValue(wx.DateTime.FromDMY(
                deadline.day, deadline.month - 1, deadline.year
            ))
            self.time.SetValue(deadline.hour)
            self.minutes.SetValue(deadline.minute)

        self.course.SetValue(data[7] if data[7] else "")
        self.topic.SetValue(data[8] if data[8] else "")
        self.resource_url.SetValue(data[9] if data[9] else "")

    def get_data(self):
        """Получение данных из формы"""
        title = self.title.GetValue()
        description = self.description.GetValue()
        priority = self.priority.GetValue()
        status = self.status.GetValue()

        date = self.deadline.GetValue()
        hour = self.time.GetValue()
        minute = self.minutes.GetValue()

        if date.IsValid():
            deadline = f"{date.GetYear()}-{date.GetMonth() + 1:02d}-{date.GetDay():02d} {hour:02d}:{minute:02d}:00"
        else:
            deadline = None

        course = self.course.GetValue()
        topic = self.topic.GetValue()
        resource_url = self.resource_url.GetValue()

        return (
            title, description, priority, status, deadline,
            course, topic, resource_url
        )


class GoalDialog(wx.Dialog):
    def __init__(self, parent, title):
        super().__init__(parent, title=title, size=(500, 450))

        self.parent = parent

        # Элементы формы
        wx.StaticText(self, label="Цель:", pos=(10, 10))
        self.title = wx.TextCtrl(self, pos=(120, 10), size=(350, -1))

        wx.StaticText(self, label="Описание:", pos=(10, 40))
        self.description = wx.TextCtrl(self, pos=(120, 40), size=(350, 100), style=wx.TE_MULTILINE)

        wx.StaticText(self, label="Приоритет:", pos=(10, 150))
        self.priority = wx.SpinCtrl(self, pos=(120, 150), size=(50, -1), min=1, max=5)

        wx.StaticText(self, label="Статус:", pos=(10, 180))
        self.status = wx.ComboBox(self, pos=(120, 180), size=(150, -1),
                                  choices=["В ожидании", "В процессе", "Достигнуто"])

        wx.StaticText(self, label="Срок:", pos=(10, 210))
        self.deadline = wx.adv.DatePickerCtrl(self, pos=(120, 210), style=wx.adv.DP_DROPDOWN | wx.adv.DP_SHOWCENTURY)
        self.time = wx.SpinCtrl(self, pos=(280, 210), size=(50, -1), min=0, max=23)
        wx.StaticText(self, label=":", pos=(335, 210))
        self.minutes = wx.SpinCtrl(self, pos=(345, 210), size=(50, -1), min=0, max=59)

        wx.StaticText(self, label="Категория:", pos=(10, 240))
        self.category = wx.TextCtrl(self, pos=(120, 240), size=(150, -1))

        wx.StaticText(self, label="Целевое значение:", pos=(10, 270))
        self.target_value = wx.TextCtrl(self, pos=(120, 270), size=(150, -1))

        wx.StaticText(self, label="Текущее значение:", pos=(10, 300))
        self.current_value = wx.TextCtrl(self, pos=(120, 300), size=(150, -1))

        # Кнопки
        btn_ok = wx.Button(self, wx.ID_OK, label="OK", pos=(300, 380))
        btn_cancel = wx.Button(self, wx.ID_CANCEL, label="Отмена", pos=(400, 380))

    def set_data(self, data):
        """Заполнение формы данными"""
        self.title.SetValue(data[1])
        self.description.SetValue(data[2] if data[2] else "")
        self.priority.SetValue(data[3])
        self.status.SetValue(data[4])

        if data[5]:
            deadline = datetime.strptime(data[5], "%Y-%m-%d %H:%M:%S")
            self.deadline.SetValue(wx.DateTime.FromDMY(
                deadline.day, deadline.month - 1, deadline.year
            ))
            self.time.SetValue(deadline.hour)
            self.minutes.SetValue(deadline.minute)

        self.category.SetValue(data[7] if data[7] else "")
        self.target_value.SetValue(str(data[8]) if data[8] is not None else "")
        self.current_value.SetValue(str(data[9]) if data[9] is not None else "")

    def get_data(self):
        """Получение данных из формы"""
        title = self.title.GetValue()
        description = self.description.GetValue()
        priority = self.priority.GetValue()
        status = self.status.GetValue()

        date = self.deadline.GetValue()
        hour = self.time.GetValue()
        minute = self.minutes.GetValue()

        if date.IsValid():
            deadline = f"{date.GetYear()}-{date.GetMonth() + 1:02d}-{date.GetDay():02d} {hour:02d}:{minute:02d}:00"
        else:
            deadline = None

        category = self.category.GetValue()

        try:
            target = float(self.target_value.GetValue()) if self.target_value.GetValue() else None
        except ValueError:
            target = None

        try:
            current = float(self.current_value.GetValue()) if self.current_value.GetValue() else 0
        except ValueError:
            current = 0

        return (
            title, description, priority, status, deadline,
            category, target, current
        )


class ReminderDialog(wx.Dialog):
    def __init__(self, parent, title):
        super().__init__(parent, title=title, size=(500, 350))

        self.parent = parent

        # Элементы формы
        wx.StaticText(self, label="Сообщение:", pos=(10, 10))
        self.message = wx.TextCtrl(self, pos=(120, 10), size=(350, 100), style=wx.TE_MULTILINE)

        wx.StaticText(self, label="Время напоминания:", pos=(10, 120))
        self.date = wx.adv.DatePickerCtrl(self, pos=(120, 120), style=wx.adv.DP_DROPDOWN | wx.adv.DP_SHOWCENTURY)
        self.time = wx.SpinCtrl(self, pos=(280, 120), size=(50, -1), min=0, max=23)
        wx.StaticText(self, label=":", pos=(335, 120))
        self.minutes = wx.SpinCtrl(self, pos=(345, 120), size=(50, -1), min=0, max=59)

        self.recurring = wx.CheckBox(self, label="Повторяющееся напоминание", pos=(10, 150))
        self.recurring.Bind(wx.EVT_CHECKBOX, self.on_recurring_check)

        wx.StaticText(self, label="Интервал:", pos=(10, 180))
        self.interval = wx.SpinCtrl(self, pos=(120, 180), size=(50, -1), min=1, max=365)
        self.interval.Disable()

        wx.StaticText(self, label="Период:", pos=(10, 210))
        self.unit = wx.ComboBox(self, pos=(120, 210), size=(150, -1),
                                choices=["минуты", "часы", "дни", "недели", "месяцы"])
        self.unit.Disable()

        # Кнопки
        btn_ok = wx.Button(self, wx.ID_OK, label="OK", pos=(300, 280))
        btn_cancel = wx.Button(self, wx.ID_CANCEL, label="Отмена", pos=(400, 280))

    def on_recurring_check(self, event):
        """Активация/деактивация элементов повторения"""
        if self.recurring.GetValue():
            self.interval.Enable()
            self.unit.Enable()
        else:
            self.interval.Disable()
            self.unit.Disable()

    def set_data(self, data):
        """Заполнение формы данными"""
        self.message.SetValue(data[1])

        if data[2]:
            remind_time = datetime.strptime(data[2], "%Y-%m-%d %H:%M:%S")
            self.date.SetValue(wx.DateTime.FromDMY(
                remind_time.day, remind_time.month - 1, remind_time.year
            ))
            self.time.SetValue(remind_time.hour)
            self.minutes.SetValue(remind_time.minute)

        if data[3]:  # is_recurring
            self.recurring.SetValue(True)
            self.interval.SetValue(data[4])
            self.unit.SetValue({
                                   "minutes": "минуты",
                                   "hours": "часы",
                                   "days": "дни",
                                   "weeks": "недели",
                                   "months": "месяцы"
                               }.get(data[5], "дни"))

            self.interval.Enable()
            self.unit.Enable()

    def get_data(self):
        """Получение данных из формы"""
        message = self.message.GetValue()

        date = self.date.GetValue()
        hour = self.time.GetValue()
        minute = self.minutes.GetValue()

        if date.IsValid():
            remind_time = f"{date.GetYear()}-{date.GetMonth() + 1:02d}-{date.GetDay():02d} {hour:02d}:{minute:02d}:00"
        else:
            remind_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        is_recurring = self.recurring.GetValue()
        interval = self.interval.GetValue() if is_recurring else None

        if is_recurring:
            unit_map = {
                "минуты": "minutes",
                "часы": "hours",
                "дни": "days",
                "недели": "weeks",
                "месяцы": "months"
            }
            unit = unit_map.get(self.unit.GetValue(), "days")
        else:
            unit = None

        return (message, remind_time, is_recurring, interval, unit)


class EmployeeDialog(wx.Dialog):
    def __init__(self, parent, title):
        super().__init__(parent, title=title, size=(400, 300))

        self.parent = parent

        # Элементы формы
        wx.StaticText(self, label="Имя:", pos=(10, 10))
        self.name = wx.TextCtrl(self, pos=(120, 10), size=(250, -1))

        wx.StaticText(self, label="Должность:", pos=(10, 40))
        self.position = wx.TextCtrl(self, pos=(120, 40), size=(250, -1))

        wx.StaticText(self, label="Email:", pos=(10, 70))
        self.email = wx.TextCtrl(self, pos=(120, 70), size=(250, -1))

        wx.StaticText(self, label="Телефон:", pos=(10, 100))
        self.phone = wx.TextCtrl(self, pos=(120, 100), size=(250, -1))

        wx.StaticText(self, label="Заметки:", pos=(10, 130))
        self.notes = wx.TextCtrl(self, pos=(120, 130), size=(250, 100), style=wx.TE_MULTILINE)

        # Кнопки
        btn_ok = wx.Button(self, wx.ID_OK, label="OK", pos=(200, 240))
        btn_cancel = wx.Button(self, wx.ID_CANCEL, label="Отмена", pos=(300, 240))

    def set_data(self, data):
        """Заполнение формы данными"""
        self.name.SetValue(data[1])
        self.position.SetValue(data[2] if data[2] else "")
        self.email.SetValue(data[3] if data[3] else "")
        self.phone.SetValue(data[4] if data[4] else "")
        self.notes.SetValue(data[5] if data[5] else "")

    def get_data(self):
        """Получение данных из формы"""
        return (
            self.name.GetValue(),
            self.position.GetValue(),
            self.email.GetValue(),
            self.phone.GetValue(),
            self.notes.GetValue()
        )


class ProjectDialog(wx.Dialog):
    def __init__(self, parent, title):
        super().__init__(parent, title=title, size=(500, 350))

        self.parent = parent

        # Элементы формы
        wx.StaticText(self, label="Название:", pos=(10, 10))
        self.name = wx.TextCtrl(self, pos=(120, 10), size=(350, -1))

        wx.StaticText(self, label="Описание:", pos=(10, 40))
        self.description = wx.TextCtrl(self, pos=(120, 40), size=(350, 100), style=wx.TE_MULTILINE)

        wx.StaticText(self, label="Дата начала:", pos=(10, 150))
        self.start_date = wx.adv.DatePickerCtrl(self, pos=(120, 150), style=wx.adv.DP_DROPDOWN | wx.adv.DP_SHOWCENTURY)

        wx.StaticText(self, label="Дата завершения:", pos=(10, 180))
        self.end_date = wx.adv.DatePickerCtrl(self, pos=(120, 180), style=wx.adv.DP_DROPDOWN | wx.adv.DP_SHOWCENTURY)

        wx.StaticText(self, label="Статус:", pos=(10, 210))
        self.status = wx.ComboBox(self, pos=(120, 210), size=(150, -1),
                                  choices=["Планирование", "В работе", "Приостановлен", "Завершен"])

        wx.StaticText(self, label="Руководитель:", pos=(10, 240))
        self.manager = wx.TextCtrl(self, pos=(120, 240), size=(250, -1))

        # Кнопки
        btn_ok = wx.Button(self, wx.ID_OK, label="OK", pos=(300, 280))
        btn_cancel = wx.Button(self, wx.ID_CANCEL, label="Отмена", pos=(400, 280))

    def set_data(self, data):
        """Заполнение формы данными"""
        self.name.SetValue(data[1])
        self.description.SetValue(data[2] if data[2] else "")

        if data[3]:  # start_date
            start_date = datetime.strptime(data[3], "%Y-%m-%d %H:%M:%S")
            self.start_date.SetValue(wx.DateTime.FromDMY(
                start_date.day, start_date.month - 1, start_date.year
            ))

        if data[4]:  # end_date
            end_date = datetime.strptime(data[4], "%Y-%m-%d %H:%M:%S")
            self.end_date.SetValue(wx.DateTime.FromDMY(
                end_date.day, end_date.month - 1, end_date.year
            ))

        self.status.SetValue(data[5] if data[5] else "Планирование")
        self.manager.SetValue(data[6] if data[6] else "")

    def get_data(self):
        """Получение данных из формы"""
        name = self.name.GetValue()
        description = self.description.GetValue()

        start_date_val = self.start_date.GetValue()
        if start_date_val.IsValid():
            start_date = f"{start_date_val.GetYear()}-{start_date_val.GetMonth() + 1:02d}-{start_date_val.GetDay():02d} 00:00:00"
        else:
            start_date = None

        end_date_val = self.end_date.GetValue()
        if end_date_val.IsValid():
            end_date = f"{end_date_val.GetYear()}-{end_date_val.GetMonth() + 1:02d}-{end_date_val.GetDay():02d} 00:00:00"
        else:
            end_date = None

        status = self.status.GetValue()
        manager = self.manager.GetValue()

        return (name, description, start_date, end_date, status, manager)


if __name__ == "__main__":
    app = wx.App(False)
    frame = TaskManagerApp()
    frame.Show()
    app.MainLoop()
