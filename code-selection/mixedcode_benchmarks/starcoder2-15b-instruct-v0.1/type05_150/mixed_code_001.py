def agc_mixed_001_01(self, commit=True):
        """
        Saves this ``form``'s cleaned_data into model instance ``self.instance``
        and related EAV attributes.

        Returns ``instance``.
        """

        if self.is_valid():
            for field_name, value in self.cleaned_data.items():
                if field_name in self.instance._meta.get_all_field_names():
                    setattr(self.instance, field_name, value)
                else:
                    self.instance.set_attribute(field_name, value)
            if commit:
                self.instance.save()
            return self.instance 

def agc_mixed_001_02(self, frame, direction):
        """ Search in one reading frame """
        if direction == "forward":
            start = frame
            end = len(self.sequence) - 2
        else:
            start = len(self.sequence) - 2 - frame
            end = -1
        for i in range(start, end, -1):
            if self.sequence[i] == "A" and self.sequence[i + 1] == "T" and self.sequence[i + 2] == "G":
                return i
        return None 

def hwc_mixed_001_03(database_name, collection_name, key):
    """Ensure Index"""

    try:
        mongodb_client_url = getattr(settings, 'MONGODB_CLIENT',
                                 'mongodb://localhost:27017/')
        mc = MongoClient(mongodb_client_url,document_class=OrderedDict)
        dbs = mc[database_name]
        dbc = dbs[collection_name]

        dbc.ensure_index(key)
        # print "success"
        return key

    except:
        # error connecting to mongodb
        # print str(sys.exc_info())
        return str(sys.exc_info()) 

def hwc_mixed_001_04(self, saturation):
        """ Set the group saturation.

        :param saturation: Saturation in decimal percent (0.0-1.0).
        """
        if saturation < 0 or saturation > 1:
            raise ValueError("Saturation must be a percentage "
                             "represented as decimal 0-1.0")
        self._saturation = saturation
        self._update_color()
        if saturation == 0:
            self.white()
        else:
            cmd = self.command_set.saturation(saturation)
            self.send(cmd) 

def hwc_mixed_001_05(self):
        """
        Find the start and end of the embedded namelist.

        Returns
        -------
        (int, int)
            start and end index for the namelist
        """
        nml_start = None
        nml_end = None
        for i in range(len(self.lines)):
            if self.lines[i].strip().startswith("&"):
                nml_start = i

            if self.lines[i].strip().startswith("/"):
                nml_end = i
        assert (
            nml_start is not None and nml_end is not None
        ), "Could not find namelist within {}".format(self.filepath)
        return nml_end, nml_start 

def agc_mixed_001_06(cls, task=None):
        """Describe available tasks or one specific task"""
        if task is None:
            print("Available tasks:")
            for task in cls.tasks:
                print(f"- {task}")
        else:
            if task in cls.tasks:
                print(f"Description of {task} task:")
                print(cls.tasks[task].__doc__)
            else:
                print(f"Task {task} not found.")
