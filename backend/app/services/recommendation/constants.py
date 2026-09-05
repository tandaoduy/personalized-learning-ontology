"""Existing catalog overrides and heuristic defaults; not ontology evidence."""

from rdflib import URIRef

# Định danh RDF
BASE_URI = "http://www.semanticweb.org/henrydao/ontologies/2025/7/TrainingProgramOntology#"

PROP_courseCode = URIRef(BASE_URI + "courseCode")
PROP_courseName = URIRef(BASE_URI + "courseName")
PROP_hasPrerequisiteCourse = URIRef(BASE_URI + "hasPrerequisiteCourse")
PROP_openSemesterType = URIRef(BASE_URI + "openSemesterType")
PROP_recommendedInSemester = URIRef(BASE_URI + "recommendedInSemester")
PROP_specializationName = URIRef(BASE_URI + "specializationName")
PROP_isRequiredForSpecialization = URIRef(BASE_URI + "isRequiredForSpecialization")
PROP_isElectiveForSpecialization = URIRef(BASE_URI + "isElectiveForSpecialization")
PROP_offeredInSpecialization = URIRef(BASE_URI + "offeredInSpecialization")
PROP_isRequiredForMajor = URIRef(BASE_URI + "isRequiredForMajor")
PROP_isElectiveForMajor = URIRef(BASE_URI + "isElectiveForMajor")
PROP_hasCredit = URIRef(BASE_URI + "hasCredit")
PROP_credit = URIRef(BASE_URI + "credit")
PROP_corequisiteWith = URIRef(BASE_URI + "corequisiteWith")

CLASS_Specialization = URIRef(BASE_URI + "Specialization")
CLASS_GeneralEducationCourse = URIRef(BASE_URI + "GeneralEducationCourse")
CLASS_PhysicalEducationCourse = URIRef(BASE_URI + "PhysicalEducationCourse")
CLASS_FoundationCourse = URIRef(BASE_URI + "FoundationCourse")

# Hằng số
REGISTER_MAX_CREDITS = 27
REGISTER_MIN_CREDITS = 10

WEIGHT_DEBT = 1000
WEIGHT_LINK = 20
WEIGHT_DELAY = 50

ELECTIVE_QUOTA_KEYS = ('general', 'physical', 'foundation', 'specialization')

ENGLISH_COURSE_CREDITS = 4
ENGLISH_COURSE_PREREQUISITES = {
    'FLS312': ['FLS310'],  # Tiếng Anh A2.1 cần A1
    'FLS313': ['FLS312'],  # Tiếng Anh A2.2 cần A2.1
    'FLS314': ['FLS313'],  # Tiếng Anh B1.1 cần A2.2
    'FLS315': ['FLS314'],  # Tiếng Anh B1.2 cần B1.1
}
ENGLISH_COURSES = frozenset({'FLS310', *ENGLISH_COURSE_PREREQUISITES.keys()})
NATIONAL_DEFENSE_COURSES = frozenset({'QPAD011', 'QPAD02', 'QPAD033', 'QPAD044'})
NON_GPA_ONE_CREDIT_COURSES = frozenset({'SOT301'})

# Môn tương đương: key = mã phụ (sẽ bị loại), value = mã chính (sẽ giữ lại)
# INT6900 và SOT348 thực chất là cùng một môn thực tập ngành
EQUIVALENT_COURSES = {
    'SOT348': 'INT6900',
}

# Môn gây nhiễu: có isElectiveForMajor=CNTT trong RDF nhưng thực chất là môn
# của ngành Cơ khí / Ô tô / Hàng hải → không bao giờ gợi ý cho sinh viên CNTT.
# (SSH, BUA, MKT, EPM vẫn được giữ vì là tự chọn hợp lệ của CNTT)
NOISE_COURSES: frozenset = frozenset({
    'AUE319',   # Nhập môn ngành Kỹ thuật ô tô
    'MAE3098',  # Nhập môn ngành KT Cơ khí động lực
    'MAE3099',  # Nhập môn ngành Khoa học hàng hải
    'MAE3207',  # Khoa học quản lý (Cơ khí)
    'MAE331',   # Kỹ thuật thủy khí
    'MEM340',   # Cơ học ứng dụng
    'MEM341',   # Đồ họa kỹ thuật (1LT, 1TH)
    'MEM342',   # Vật liệu học
    'MEM347',   # Vẽ kỹ thuật (2LT+1TH)
    'EPM320',   # Con người và môi trường
    'SH1',      # Sinh hoạt Cuối tuần - nhà trường tự thêm, không cần gợi ý
    'SSH380',   # Văn hóa Việt Nam - Môn nhiễu
})


