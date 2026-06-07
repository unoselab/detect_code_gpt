def agc_mixed_002_01(self, path, apps_models):
        """
        Print each app in apps_models associative list into its own file.
        """
        for app_name, models in apps_models.items():
            app_path = os.path.join(path, app_name)
            if not os.path.exists(app_path):
                os.makedirs(app_path)
            for model_name, model in models.items():
                model_path = os.path.join(app_path, model_name)
                with open(model_path, 'w') as f:
                    f.write(model) 

def hwc_mixed_002_02(cls, sock, chunk_type, isatty, chunk_eof_type=None, buf_size=None, select_timeout=None):
    """Yields the write side of a pipe that will copy appropriately chunked values to a socket."""
    with cls.open_multi(sock,
                        (chunk_type,),
                        (isatty,),
                        chunk_eof_type,
                        buf_size,
                        select_timeout) as ctx:
      yield ctx 

def agc_mixed_002_03(self, prefix="", new_path=None, in_place=True, remove_desc=True):
        """Rename every sequence based on a prefix."""
        # Temporary path #
        if new_path is None:
            new_path = self.path
        if not in_place:
            new_path = os.path.join(os.path.dirname(new_path),
                                    os.path.basename(new_path).replace(self.path, ""))
        if not os.path.exists(new_path):
            os.makedirs(new_path)
        for seq in self.sequences:
            seq.rename(prefix=prefix, new_path=new_path, in_place=in_place, remove_desc=remove_desc) 

def hwc_mixed_002_04(self, visibility, mode="add"):
        """Return the AR fields with the current visibility
        """
        ar = self.get_ar()
        mv = api.get_view("ar_add_manage", context=ar)
        mv.get_field_order()

        out = []
        for field in mv.get_fields_with_visibility(visibility, mode):
            # check custom field condition
            visible = self.is_field_visible(field)
            if visible is False and visibility != "hidden":
                continue
            out.append(field)
        return out 

def agc_mixed_002_05(name, app=None, components=None, raw=False):
    """
    Discover any named attributes, modules, or packages and coalesces the
    results.

    Looks in any module or package declared in the the 'COMPONENTS' key
    in the application config.

    Order of found results are persisted from the order that the
    component was declared in.

    @param[in] components
        An array of components; overrides any setting in the application
        config.

    @param[in] raw
        If True then no processing is done on the found items.
    """

    if app is None:
        app = get_app()

    if components is None:
        components = app.config.get('COMPONENTS', [])

    found = []
    for component in components:
        if component in app.components:
            found.append(app.components[component])
        elif component in app.modules:
            found.append(app.modules[component])
        elif component in app.packages:
            found.append(app.packages[component])

    if raw:
        return found

    return coalesce(found, name) 

def hwc_mixed_002_06(self, msg):
        """decrypt a message"""
        error = False
        signature = msg[0:SHA256.digest_size]
        iv = msg[SHA256.digest_size:SHA256.digest_size + AES.block_size]
        cipher_text = msg[SHA256.digest_size + AES.block_size:]
        if self.sign(iv + cipher_text) != signature:
            error = True
        ctr = Counter.new(AES.block_size * 8, initial_value=self.bin2long(iv))
        cipher = AES.AESCipher(self._cipherkey, AES.MODE_CTR, counter=ctr)
        plain_text = cipher.decrypt(cipher_text)
        if error:
            raise DecryptionError
        return plain_text
