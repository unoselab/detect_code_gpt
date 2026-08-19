def hwc_mixed_005_01(element_tree):
    """Return an XML Element.

        Args:
            element_tree (Element): XML Element to be returned.  If sent as a
                ``str``, this function will attempt to convert it to an
                ``Element``.

        Returns:
            Element: An XML Element.

        Raises:
            TypeError: if `element_tree` is not of type ``Element`` and it
                cannot be converted from a ``str``.

        Examples:
            >>> import pynos.utilities
            >>> import xml.etree.ElementTree as ET
            >>> ele = pynos.utilities.return_xml(ET.Element('config'))
            >>> assert isinstance(ele, ET.Element)
            >>> ele = pynos.utilities.return_xml('<config />')
            >>> assert isinstance(ele, ET.Element)
            >>> ele = pynos.utilities.return_xml(
            ... ['hodor']) # doctest: +IGNORE_EXCEPTION_DETAIL
            Traceback (most recent call last):
            TypeError
    """
    if isinstance(element_tree, ET.Element):
        return element_tree
    try:
        return ET.fromstring(element_tree)
    except TypeError:
        raise TypeError('{} takes either {} or {} type.'
                        .format(repr(return_xml.__name__),
                                repr(str.__name__),
                                repr(ET.Element.__name__))) 

def agc_mixed_005_02(self, v_indices, as_boolean=False):
        """
        returns all of the faces that contain at least one of the vertices in v_indices
        """
        if as_boolean:
            mask = np.zeros(len(self.faces), dtype=bool)
            for v in v_indices:
                mask |= np.any(self.faces == v, axis=1)
            return mask

        face_indices = set()
        for v in v_indices:
            matches = np.where(np.any(self.faces == v, axis=1))[0]
            face_indices.update(matches)
        return np.array(sorted(list(face_indices)), dtype=int) 

def hwc_mixed_005_03(fig, update_figure, filename, title, fps=15, dpi=100):
    """Helps us to create a movie."""
    FFMpegWriter = manimation.writers['ffmpeg']
    metadata     = dict(title=title)
    writer       = FFMpegWriter(fps=fps, metadata=metadata)

    with writer.saving(fig, filename, dpi):
        t = 0
        while True:
            if update_figure(t):
                writer.grab_frame()
                t += 1
            else:
                break 

def hwc_mixed_005_04(self, X):
        """
        Transform the segmented time series data into feature data.
        If contextual data is included in X, it is returned with the feature data.

        Parameters
        ----------
        X : array-like, shape [n_series, ...]
            Segmented time series data and (optionally) contextual data

        Returns
        -------
        X_new : array shape [n_series, ...]
            Feature representation of segmented time series data and contextual data

        """
        self._validate()

        Xt, Xc = get_ts_data_parts(X)
        check_array(Xt, dtype='numeric', ensure_2d=False, allow_nd=True)

        # calculated features
        fts = np.column_stack([trans.transform(self._select(Xt, cols))
                               for _, trans, cols in self.transformers])
        # contextual features
        if Xc is not None:
            fts = np.column_stack([fts, Xc])

        return fts 

def agc_mixed_005_05():
    """
    Template tag that renders the needed css files for the theming app.
    """
    from django import template
    from django.utils.safestring import mark_safe

    register = template.Library()

    @register.simple_tag
    def render_theming_css():
        """
        Template tag that renders the needed css files for the theming app.
        """
        css_files = [
            '/static/theming/css/base.css',
            '/static/theming/css/theme.css',
        ]
        links = '\n'.join([f'<link rel="stylesheet" href="{url}">' for url in css_files])
        return mark_safe(links) 

def agc_mixed_005_06(self, lines):
        """ Build the map of the various segments.
        Each segment has a qualified name according to the number
        of equivalent segment.
        If there is only one segment, the segment name is MSH[1] or PID[1].
        If there are 3 segments with the same name, the qualified names are
        SPM[1], SPM[2], SPM[3] for instance.
        SPM[2] is the second SPM segment.

        """
        segment_map = {}
        counts = {}
        for line in lines:
            if not line:
                continue
            segment_name = line.split('[')[0].split(' ')[0].split('|')[0]
            counts[segment_name] = counts.get(segment_name, 0) + 1
            qualified_name = f"{segment_name}[{counts[segment_name]}]"
            segment_map[qualified_name] = line
        return segment_map
