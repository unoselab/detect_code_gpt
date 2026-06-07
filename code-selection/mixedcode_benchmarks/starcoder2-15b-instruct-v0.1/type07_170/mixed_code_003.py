def hwc_mixed_003_01( self, name, block_height, **con_info ):
        """
        Get all the states the name was in at a particular block height.
        Does NOT work on expired names.
        Return {'status': true, 'record': ...}
        """
        if not check_name(name):
            return {'error': 'invalid name', 'http_status': 400}

        if not check_block(block_height):
            return self.success_response({'record': None})

        db = get_db_state(self.working_dir)
        names_at = db.get_name_at( name, block_height, include_expired=False )
        db.close()

        ret = []
        for name_rec in names_at:
            if 'opcode' not in name_rec:
                name_rec['opcode'] = op_get_opcode_name(name_rec['op'])

            ret.append(self.sanitize_rec(name_rec))

        return self.success_response( {'records': ret} ) 

def agc_mixed_003_02(self, name, data_type=None, default_value=None, scoped_variable_id=None):
        """ Adds a scoped variable to the container state

        :param name: The name of the scoped variable
        :param data_type: An optional data type of the scoped variable
        :param default_value: An optional default value of the scoped variable
        :param scoped_variable_id: An optional scoped variable id of the
        :return: the unique id of the added scoped variable
        :raises exceptions.ValueError: if the scoped variable is not valid
        """
        if not name:
            raise ValueError("Invalid scoped variable: name is required")
        if scoped_variable_id and not isinstance(scoped_variable_id, int):
            raise ValueError("Invalid scoped variable: scoped_variable_id must be an integer")
        scoped_variable = {
            "name": name,
            "data_type": data_type,
            "default_value": default_value,
            "scoped_variable_id": scoped_variable_id or self.next_scoped_variable_id,
        }
        self.scoped_variables.append(scoped_variable)
        self.next_scoped_variable_id += 1
        return scoped_variable["scoped_variable_id"] 

def hwc_mixed_003_03(module_name=None, module=None, register=True):
    """ finds module in sys.modules based on module name unless the module has
    already been found and is passed in """
    if module is None and module_name is not None:
        try:
            module = sys.modules[module_name]
        except KeyError as ex:
            print(ex)
            raise KeyError(('module_name=%r must be loaded before ' +
                            'receiving injections') % module_name)
    elif module is not None and module_name is None:
        pass
    else:
        raise ValueError('module_name or module must be exclusively specified')
    if register is True:
        _add_injected_module(module)
    return module 

def agc_mixed_003_04(in_file, data, max_distance=10000, work_dir=None):
    """Add gene annotations to a BED file from pre-prepared RNA-seq data.

    max_distance -- only keep annotations within this distance of event
    """
    with open(in_file, 'r') as f:
        lines = f.readlines()

    for line in lines:
        fields = line.split('\t')
        if len(fields) >= 4:
            event_start = int(fields[1])
            event_end = int(fields[2])
            for gene_start, gene_end, gene_name in data:
                if abs(event_start - gene_start) <= max_distance or abs(event_end - gene_end) <= max_distance:
                    fields.append(gene_name)
                    break

    return '\n'.join('\t'.join(fields) for fields in lines) 

def agc_mixed_003_05(self):
        """
        Request URL and parse response. Yield a ``Torrent`` for every torrent
        on page.
        """
        response = requests.get(self.url)
        html = response.text
        soup = BeautifulSoup(html, 'html.parser')
        torrents = soup.find_all('div', class_='torrent')
        for torrent in torrents:
            yield Torrent(
                title=torrent.find('div', class_='title').text,
                size=torrent.find('div', class_='size').text,
                seeds=torrent.find('div', class_='seeds').text,
                leeches=torrent.find('div', class_='leeches').text,
                download_url=torrent.find('a', class_='download')['href'],
            ) 

def hwc_mixed_003_06(content_type_pk, obj_pk):
    """
    Unbuild all views related to a object and then sync to S3.

    Accepts primary keys to retrieve a model object that
    inherits bakery's BuildableModel class.
    """
    ct = ContentType.objects.get_for_id(content_type_pk)
    obj = ct.get_object_for_this_type(pk=obj_pk)
    try:
        # Unbuild the object
        logger.info("unpublish_object task has received %s" % obj)
        obj.unbuild()
        # Run the `publish` management command unless the
        # ALLOW_BAKERY_AUTO_PUBLISHING variable is explictly set to False.
        if not getattr(settings, 'ALLOW_BAKERY_AUTO_PUBLISHING', True):
            logger.info("Not running publish command because \
ALLOW_BAKERY_AUTO_PUBLISHING is False")
        else:
            management.call_command("publish")
    except Exception:
        # Log the error if this crashes
        logger.error("Task Error: unpublish_object", exc_info=True)
