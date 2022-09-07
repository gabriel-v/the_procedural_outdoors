from abc import ABC, abstractmethod


class SceneGeneratorInterface(ABC):
    @abstractmethod
    def generate_background_scene(self, scene):
        pass

    @abstractmethod
    def init_scene_parameters(self, scene):
        pass

    @abstractmethod
    def frame_callback(self, scene, render_data=None):
        pass
