import multiprocessing

RESOLUTION_X = 640
RESOLUTION_Y = 480

# RESOLUTION_X = int(960 / 6)
# RESOLUTION_Y = int(540 / 6)
MAX_FRAMES = 120

RANDOM_TREE_COUNT = 20

RENDER_TREES = True
RENDER_CLOUDS = True
RENDER_BUILDINGS = True

CAMERA_LENS = 33.3
CAMERA_CLIP_START = 0.1
CAMERA_CLIP_END = 70000
SAMPLES_PER_PIXEL = 11
RENDER_TIME_LIMIT = 222
# RENDER_TILE_SIZE = 4096
RENDER_THREAD_COUNT = multiprocessing.cpu_count()

CAMERA_ENABLE_VIEW_CULLING = False
CAMERA_ENABLE_BACKFACE_CULLING = False

SIMULATION_FPS = 12
CAMERA_ANIMATION_SPEED_KMH = 45
CAMERA_ANIMATION_SPEED_M_S = CAMERA_ANIMATION_SPEED_KMH / 3.6

MAIN_BLEND_FILE = "output/trains.blend"

GEOMETRY_INPUT_FILE = 'output/trains.blend'
# GEOMETRY_INPUT_FILE = 'cube/tmp/geometry.blend'
GEOMETRY_SAVE_FILE = 'cube/geometry.blend'
# GEOMETRY_SAVE_FILE_2 = 'cube/saved-geometry-2.blend'

SEGMENTATION_IDS = {
    "building": 1,
    "terrain": 2,
    "vegetation": 3,
    "rails_metal": 4,
    "rails_planks": 5,
    "signs": 6,
}
