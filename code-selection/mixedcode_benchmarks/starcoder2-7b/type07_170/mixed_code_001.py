def agc_mixed_001_01(self, pk=None, **filters):
        """ Retrieve an object instance. If a single argument is supplied, object is queried by
        primary key, else filter queries will be applyed.
        If more than one object was found raise MultipleObjectsReturned.
        If no object found, raise DoesNotExist.
        Raise PermissionDenied if user has no permission 'view' on object.

        See https://docs.djangoproject.com/en/dev/ref/models/querysets/#get for more details
        """
        if pk:
            try:
                return self.get_queryset().get(pk=pk)
            except self.model.DoesNotExist:
                raise DoesNotExist
        else:
            try:
                return self.get_queryset().get(**filters)
            except self.model.DoesNotExist:
                raise DoesNotExist
            except self.model.MultipleObjectsReturned:
                raise MultipleObjectsReturned 

def hwc_mixed_001_02(self, val_list):
        """Formats value list from Munin Graph and returns multi-line value
        entries for the plugin fetch cycle.

        @param val_list: List of name-value pairs. 
        @return:         Multi-line text.

        """
        vals = []
        for (name, val) in val_list:
            if val is not None:
                if isinstance(val, float):
                    vals.append("%s.value %f" % (name, val))
                else:
                    vals.append("%s.value %s" % (name, val))
            else:
                vals.append("%s.value U" % (name,))
        return "\n".join(vals) 

def hwc_mixed_001_03(name='default', **kwargs):
    """
    Request power state change

    name = ``default``
        * network -- Request network boot
        * hd -- Boot from hard drive
        * safe -- Boot from hard drive, requesting 'safe mode'
        * optical -- boot from CD/DVD/BD drive
        * setup -- Boot into setup utility
        * default -- remove any IPMI directed boot device request

    kwargs
        - api_host=localhost
        - api_user=admin
        - api_pass=
        - api_port=623
        - api_kg=None
    """
    ret = {'name': name, 'result': False, 'comment': '', 'changes': {}}
    org = __salt__['ipmi.get_bootdev'](**kwargs)
    if 'bootdev' in org:
        org = org['bootdev']

    if org == name:
        ret['result'] = True
        ret['comment'] = 'system already in this state'
        return ret

    if __opts__['test']:
        ret['comment'] = 'would change boot device'
        ret['result'] = None
        ret['changes'] = {'old': org, 'new': name}
        return ret

    outdddd = __salt__['ipmi.set_bootdev'](bootdev=name, **kwargs)
    ret['comment'] = 'changed boot device'
    ret['result'] = True
    ret['changes'] = {'old': org, 'new': name}
    return ret 

def hwc_mixed_001_04(self, path):
        """
        Load cookies from the file.

        Content of file should be a JSON-serialized list of dicts.
        """

        with open(path) as inf:
            data = inf.read()
            if data:
                items = json.loads(data)
            else:
                items = {}
        for item in items:
            extra = dict((x, y) for x, y in item.items()
                         if x not in ['name', 'value', 'domain'])
            self.set(item['name'], item['value'], item['domain'], **extra) 

def agc_mixed_001_05(self, node):
        """ Apply transformation and return if an update happened. """
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Attribute):
                if node.func.attr == 'get':
                    if isinstance(node.args[0], ast.Str):
                        if node.args[0].s in self.config:
                            node.args = [ast.Str(self.config[node.args[0].s])]
                            return True
        return False 

def agc_mixed_001_06(self):
        """
        Perform actions based on CLI options

        @returns: status code
        """
        if self.options.list:
            self.list_all()
        elif self.options.get:
            self.get_one()
        elif self.options.create:
            self.create()
        elif self.options.update:
            self.update()
        elif self.options.delete:
            self.delete()
        elif self.options.help:
            self.print_help()
        else:
            self.print_help()
            return 1

        return 0
