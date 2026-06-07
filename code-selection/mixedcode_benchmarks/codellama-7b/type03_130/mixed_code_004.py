def hwc_mixed_004_01(self, conf, images):
        """Stop the containers for all our dependencies"""
        for dependency, _ in conf.dependency_images():
            self.stop_deps(images[dependency], images)
            try:
                self.stop_container(images[dependency], fail_on_bad_exit=True, fail_reason="Failed to run dependency container")
            except BadImage:
                raise
            except Exception as error:
                log.warning("Failed to stop dependency container\timage=%s\tdependency=%s\tcontainer_name=%s\terror=%s", conf.name, dependency, images[dependency].container_name, error) 

def agc_mixed_004_02(self, mod_fullname, path=None):
        """ mod_fullname doubles as the name of the VARIABLE holding our new sh
        context.  for example:

            derp = sh()
            from derp import ls

        here, mod_fullname will be "derp".  keep that in mind as we go throug
        the rest of this function """

        if not mod_fullname.startswith(self.sh_name):
            return

        # if we're in the sh context, but the name is not a valid sh command,
        # we're not interested
        if mod_fullname not in self.sh_commands:
            return

        # if we're in the sh context, and the name is a valid sh command, we
        # need to return a loader for the command
        return self 

def hwc_mixed_004_03(self):
        """ Write lines for instantiation """
        # e.g. model_name_35 = Model()
        code_lines = []

        if not self.instantiated:
            code_lines.append("%s = %s()" % (self.variable_name, self.model.__name__))
            self.instantiated = True

            # Store our variable name for future foreign key references
            pk_name = self.instance._meta.pk.name
            key = '%s_%s' % (self.model.__name__, getattr(self.instance, pk_name))
            self.context[key] = self.variable_name

        return code_lines 

def agc_mixed_004_04(self, other):
        """Return false if suffixes are mutually exclusive"""

        # If suffix is omitted, assume a match
        if self.suffix == other.suffix:
            return True
        if self.suffix is None:
            return False
        if other.suffix is None:
            return False
        if self.suffix.startswith(other.suffix):
            return True
        if other.suffix.startswith(self.suffix):
            return False
        return False 

def agc_mixed_004_05(self, whole=False):
        """
        internal method, delete all append items (ends with +)
        :param whole: pass thru 'whole' param to climb
        :return: None
        """
        if whole:
            for i in self.items:
                i.__remove_append_items(whole=True)
        else:
            if self.items:
                for i in self.items:
                    if i.name.endswith('+'):
                        self.items.remove(i) 

def hwc_mixed_004_06(nsteps):
        """Returns the number of operations needed for nsteps of GMRES"""
        return {'A': 1 + nsteps,
                'M': 2 + nsteps,
                'Ml': 2 + nsteps,
                'Mr': 1 + nsteps,
                'ip_B': 2 + nsteps + nsteps*(nsteps+1)/2,
                'axpy': 4 + 2*nsteps + nsteps*(nsteps+1)/2
                }
