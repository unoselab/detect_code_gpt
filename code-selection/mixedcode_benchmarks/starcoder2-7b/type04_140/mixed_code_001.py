def hwc_mixed_001_01(self, event):
        """Update rotation parmeters based on mouse movement"""
        p2 = event.mouse_event.pos
        if self._event_value is None:
            self._event_value = p2
        wh = self._viewbox.size
        self._quaternion = (Quaternion(*_arcball(p2, wh)) *
                            Quaternion(*_arcball(self._event_value, wh)) *
                            self._quaternion)
        self._event_value = p2
        self.view_changed() 

def agc_mixed_001_02(x):
    """Faster version of np.unique().

    This version is restricted to 1D arrays of non-negative integers.

    It is only faster if len(x) >> len(unique(x)).

    """
    x = np.asarray(x)
    if x.ndim!= 1:
        raise ValueError('x must be 1-dimensional')
    if x.dtype.kind not in 'iu':
        raise ValueError('x must be an array of non-negative integers')
    if x.size == 0:
        return x
    x = np.sort(x)
    last = x[0]
    y = [last]
    for i in x[1:]:
        if i!= last:
            y.append(i)
            last = i
    return np.array(y, dtype=x.dtype) 

def hwc_mixed_001_03(self, features, locus):
        """
        creates GFE from HLA sequence and locus

        :param locus: string containing HLA locus.
        :param sequence: string containing sequence data.

        :return: GFEobject.
        """
        gfe_list = []
        for feat in sorted(self.structures[locus],
                           key=lambda k: self.structures[locus][k]):
            acc = str(0)
            if feat in features:
                acc = str(features[feat])
            gfe_list.append(acc)

        gfea = '-'.join(gfe_list)
        return locus + "w" + gfea 

def agc_mixed_001_04(self, mesh):
        """
        Compute the minimum distance between each point of a mesh and the great
        circle arcs perpendicular to the average strike direction of the
        fault trace and passing through the end-points of the trace.

        :param mesh:
            :class:`~openquake.hazardlib.geo.mesh.Mesh` of points to calculate
            Ry0-distance to.
        :returns:
            Numpy array of distances in km.
        """
        # This computes ry0 by using an average strike direction
        strike = self.get_strike()
        # get the end-points of the fault trace
        end_points = self.get_end_points()
        # get the great circle arcs perpendicular to the average strike
        # direction of the fault trace and passing through the end-points
        # of the trace
        great_circle_arcs = self.get_great_circle_arcs()
        # get the minimum distance between each point of the mesh and the
        # great circle arcs
        return mesh.get_ry0_distance(strike, end_points, great_circle_arcs) 

def hwc_mixed_001_05(name, import_alias_mapping):
    """Returns either None or the handled alias.
    Used in add_module.
    """
    for key, val in import_alias_mapping.items():
        # e.g. Foo == Foo
        # e.g. Foo.Bar startswith Foo.
        if name == val or \
                name.startswith(val + '.'):

            # Replace val with key in name
            # e.g. StarbucksVisitor.Tea -> Eataly.Tea because
            #   "from .nested_folder import StarbucksVisitor as Eataly"
            return name.replace(val, key)
    return None 

def agc_mixed_001_06(
            metar: typing.Union[str, 'CustomMetar']
    ) -> typing.Tuple[typing.Union[str, None], typing.Union['CustomMetar', None]]:
        """
        Builds a CustomMetar object from a CustomMetar object (returns it), an ICAO code or a METAR string

        Args:
            metar: CustomMetar object, ICAO string or METAR string

        Returns: CustomMetar object

        """
        if isinstance(metar, CustomMetar):
            return metar, None
        elif isinstance(metar, str):
            if len(metar) == 4:
                return None, CustomMetar(metar)
            else:
                return CustomMetar(metar), None
        else:
            raise TypeError("metar must be a CustomMetar object, an ICAO code or a METAR string")
