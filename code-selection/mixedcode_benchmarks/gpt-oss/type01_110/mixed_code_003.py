def hwc_mixed_003_01(self, name):
        """
        Load and return a module

        Always returns the corresponding module. If the module is already
        loaded, the existing module is returned.
        """
        if name in sys.modules:
            return sys.modules[name]
        path = self.module2uri(name)
        if os.path.isfile(path):
            return self._load_module(name, path)
        elif os.path.isdir(path):
            return self._load_package(name, path)
        else:
            raise ImportError("Missing module source file %r" % path) 

def agc_mixed_003_02(genes, custom_spont_id=None):
    """Return the DictList of genes that are not spontaneous in a model.

    Args:
        genes (DictList): Genes DictList
        custom_spont_id (str): Optional custom spontaneous ID if it does not match the regular expression ``[Ss](_|)0001``

    Returns:
        DictList: genes excluding ones that are spontaneous

    """
    import re
    pattern = re.compile(r'^[Ss]_?0001$')
    filtered = [
        gene
        for gene in genes
        if not (
            pattern.match(getattr(gene, "id", None))
            or (custom_spont_id is not None and getattr(gene, "id", None) == custom_spont_id)
        )
    ]
    return type(genes)(filtered) 

def hwc_mixed_003_03(self, image):
        """Delete the file of the given ``image``.

        :param image: the image to delete
        :type image: :class:`sqlalchemy_imageattach.entity.Image`

        """
        from .entity import Image
        if not isinstance(image, Image):
            raise TypeError('image must be a sqlalchemy_imageattach.entity.'
                            'Image instance, not ' + repr(image))
        self.delete_file(image.object_type, image.object_id,
                         image.width, image.height, image.mimetype) 

def hwc_mixed_003_04(self, index):
        """
        Get the string with the given index from the device
        """
        max_len = 128
        str_buf = ffi.new("wchar_t[]", str(bytearray(max_len)))
        ret = hidapi.hid_get_indexed_string(self._device, index, str_buf, max_len)

        if ret < 0:
            raise HIDException(self._device.get_error())
        elif ret == 0:
            return None
        else:
            return ffi.string(str_buf).encode('utf-8') 

def agc_mixed_003_05(self,value):
        """
        Convert a numerical value into an integer, then to a bytes object. Check
        bounds for unsigned int.
        """
        # Coerce to int. This will throw a ValueError if the value can't 
        # actually be converted.
        try:
            iv = int(value)
        except Exception as e:
            raise TypeError(f"Value {value!r} cannot be converted to int") from e
        if iv < 0 or iv > 0xFFFFFFFF:
            raise ValueError(f"Unsigned int value out of range: {iv}")
        return iv.to_bytes(4, byteorder='big', signed=False) 

def agc_mixed_003_06(self):
        """
        Returns the private-config file for this IOU VM.

        :returns: path to config file. None if the file doesn't exist
        """

        import os
        from pathlib import Path

        base = getattr(self, "_path", None) or getattr(self, "path", None)
        if not base:
            return None
        if isinstance(base, str):
            base = Path(base)
        cfg_path = base / "private-config"
        return str(cfg_path) if cfg_path.is_file() else None
