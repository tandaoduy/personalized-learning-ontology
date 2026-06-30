"""
Configuration for Flask Application
"""

import os

class Config:
    """Base Configuration"""
    
    # Cấu hình Flask
    DEBUG = True
    TESTING = False
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'
    
    # Đường dẫn - Tạo động theo vị trí file hiện tại
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    
    ONTOLOGY_PATH = os.path.join(BASE_DIR, 'owl', 'current', 'ontology_v19.rdf')
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
    STUDY_GOALS = ['đúng hạn', 'giảm tải', 'học vượt']
    
    # Ngành học
    MAJORS = ['Công Nghệ Thông Tin', 'Kỹ Thuật Phần Mềm', 'Khoa Học Dữ Liệu']


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
