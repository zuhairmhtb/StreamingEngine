class File(object):
    def __init__(self, file:bytes, content_type:str):
        self.file = file
        self.content_type = content_type
