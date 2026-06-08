def agc_mixed_001_01(self, bucket_name, bucket_region, storage_type, statistic, days):
        """ Returns datapoints from cloudwatch for bucket statistics.

        Args:
            bucket_name `(str)`: The name of the bucket
            statistic `(str)`: The statistic you want to fetch from
            days `(int)`: Sample period for the statistic

        """

        try:
            # Get the bucket region
            region = self.get_bucket_region(bucket_name)
            # Get the bucket statistics
            statistics = self.get_bucket_statistics(bucket_name, bucket_region, storage_type, statistic, days)
            # Return the statistics
            return statistics
        except Exception as e:
            # Log the exception
            self.logger.exception(e)
            # Raise the exception
            raise 

def hwc_mixed_001_02(self, path):
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

def agc_mixed_001_03(self, val):
        """Helper function to format a value."""
        if isinstance(val, str):
            return val
        elif isinstance(val, bool):
            return 'true' if val else 'false'
        elif isinstance(val, int):
            return str(val)
        elif isinstance(val, float):
            return str(val)
        elif isinstance(val, list):
            return ','.join(val)
        elif isinstance(val, dict):
            return ','.join(val.keys())
        else:
            raise ValueError('Invalid value type: {}'.format(type(val))) 

def agc_mixed_001_04(self, tops):
        """
        The default merging strategy. The base env is authoritative, so it is
        checked first, followed by the remaining environments. In top files
        from environments other than "base", only the section matching the
        environment from the top file will be considered, and it too will be
        ignored if that environment was defined in the "base" top file.
        """
        merged = {}
        for top in tops:
            for section, items in top.items():
                if section == "base":
                    merged.update(items)
                elif section in merged:
                    merged[section].update(items)
                else:
                    merged[section] = items
        return merged 

def hwc_mixed_001_05(p):
    """ function_body : program_co END FUNCTION
                      | program_co END SUB
                      | statements_co END FUNCTION
                      | statements_co END SUB
                      | co_statements_co END FUNCTION
                      | co_statements_co END SUB
                      | END FUNCTION
                      | END SUB
    """
    if not FUNCTION_LEVEL:
        syntax_error(p.lineno(3), "Unexpected token 'END %s'. No Function or Sub has been defined." % p[2])
        p[0] = None
        return

    a = FUNCTION_LEVEL[-1].kind
    if a not in (KIND.sub, KIND.function):  # This function/sub was not correctly declared, so exit now
        p[0] = None
        return

    i = 2 if p[1] == 'END' else 3
    b = p[i].lower()

    if a != b:
        syntax_error(p.lineno(i), "Unexpected token 'END %s'. Should be 'END %s'" % (b.upper(), a.upper()))
        p[0] = None
    else:
        p[0] = None if p[1] == 'END' else p[1] 

def hwc_mixed_001_06(keyword, feature, parent):
    """Given a keyword, it will return the value of the keyword
    from the hazard layer's extra keywords.

    For instance:
    *   hazard_extra_keyword( 'depth' ) -> will return the value of 'depth'
        in current hazard layer's extra keywords.
    """
    _ = feature, parent  # NOQA
    hazard_layer_path = QgsExpressionContextUtils. \
        projectScope(QgsProject.instance()).variable(
          'hazard_layer')
    hazard_layer = load_layer(hazard_layer_path)[0]
    keywords = KeywordIO.read_keywords(hazard_layer)
    extra_keywords = keywords.get('extra_keywords')
    if extra_keywords:
        value = extra_keywords.get(keyword)
        if value:
            value_definition = definition(value)
            if value_definition:
                return value_definition['name']
            return value
        else:
            return tr('Keyword %s is not found' % keyword)
    return tr('No extra keywords found')
