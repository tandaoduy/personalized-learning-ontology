"""
Configuration for Flask Application
"""

import os
from datetime import timedelta


APP_ENV = os.environ.get("APP_ENV", "development").strip().lower()

class Config:
    """Base Configuration"""
    
    # Cấu hình Flask
    DEBUG = APP_ENV == "development"
    TESTING = False
    SECRET_KEY = os.environ.get("SECRET_KEY") or (
        "dev-secret-key-change-in-production" if DEBUG else None
    )
    PERMANENT_SESSION_LIFETIME = timedelta(minutes=60)
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = not DEBUG
    MAX_CONTENT_LENGTH = 1 * 1024 * 1024
    
    # Đường dẫn - Tạo động theo vị trí file hiện tại
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    
    ONTOLOGY_PATH = os.path.join(BASE_DIR, 'owl', 'ontology_v23.rdf')
    STUDENT_DATA_JSON = os.path.join(BASE_DIR, 'data', 'DanhSachSinhVien.json')
    STUDENT_DATA_CSV = os.path.join(BASE_DIR, 'data', 'DanhSachSinhVien.csv')
    
    # Tham số bộ máy gợi ý
    BEAM_WIDTH = 8
    REGISTER_MAX_CREDITS = 27
    REGISTER_MIN_CREDITS = 10
    
    # Trọng số tính điểm
    WEIGHT_DEBT = 1000
    WEIGHT_LINK = 20
    WEIGHT_DELAY = 50
    
    # Hạn ngạch môn tự chọn (mặc định - có thể tùy chỉnh theo mục tiêu học)
    ELECTIVE_QUOTAS = {
        'general': 1,           # Môn đại cương tự chọn
        'physical': 2,          # Môn thể chất tự chọn
        'foundation': 1,        # Môn cơ sở ngành tự chọn
        'specialization': 3,    # Môn chuyên ngành tự chọn
    }
    
    # Mục tiêu học tập
    STUDY_GOALS = ['đúng hạn', 'học vượt']
    
    # Ngành học. Chuyên ngành được quản lý riêng, không đặt cùng cấp với ngành.
    MAJORS = ['Công Nghệ Thông Tin', 'Khoa học máy tính']
    SPECIALIZATIONS_BY_MAJOR = {
        'Công Nghệ Thông Tin': [
            'Công nghệ phần mềm',
            'Hệ Thống Thông Tin',
            'Truyền thông và Mạng máy tính',
        ],
        'Khoa học máy tính': [
            'Trí tuệ nhân tạo',
            'Khoa học dữ liệu',
        ],
    }


class DevelopmentConfig(Config):
    """Development Configuration"""
    DEBUG = True
    TESTING = False


class TestingConfig(Config):
    """Testing Configuration"""
    TESTING = True
    DEBUG = True


class ProductionConfig(Config):
    """Production Configuration"""
    DEBUG = False
    TESTING = False
