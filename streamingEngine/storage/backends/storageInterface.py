import abc
from typing import IO, Any
from .file import File
from typing import Union


class IStorageInterface(abc.ABC):

    @classmethod
    def __subclasscheck__(cls, subclass):
        return (
            hasattr(subclass, 'does_file_exist') and
            callable(subclass.does_file_exist) and

            hasattr(subclass, 'upload_file') and
            callable(subclass.does_file_exist) and

            hasattr(subclass, 'get_file') and
            callable(subclass.does_file_exist) and

            hasattr(subclass, 'delete_file') and
            callable(subclass.does_file_exist) and

            hasattr(subclass, 'copy_file') and
            callable(subclass.does_file_exist) and

            hasattr(subclass, 'move_file') and
            callable(subclass.does_file_exist) or
            NotImplemented
        )

    @classmethod
    def does_file_exist(cls, basedir: str, path: str, *args, **kwargs) -> bool:
        raise NotImplementedError

    @classmethod
    def upload_file(cls, basedir: str, data: Union[IO[Any], str], path: str, content_type: str,
                    use_concurrency: bool, create_basedir_if_not_exist:bool, *args, **kwargs) -> bool:
        raise NotImplementedError


    @classmethod
    def get_file(cls, basedir: str, path: str, *args, **kwargs) ->File:
        raise NotImplementedError


    @classmethod
    def delete_file(cls, basedir: str, path: str, *args, **kwargs) -> bool:
        raise NotImplementedError

    @classmethod
    def copy_file(cls, source_basedir: str, source_path: str, destination_basedir, destination_path: str,
                  overwrite: bool, *args, **kwargs) -> bool:
        raise NotImplementedError

    @classmethod
    def move_file(cls, source_basedir: str, source_path: str, destination_basedir, destination_path: str,
                  overwrite: bool, *args, **kwargs) -> bool:
        raise NotImplementedError

