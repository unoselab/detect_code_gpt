def agc_mixed_005_01(self, slicer=None, na_rep='nan', quoting=None,
                        **kwargs):
        """ convert to our native types format, slicing if desired """

        if slicer is not None:
            slicer = self._slice(slicer)
        return self._engine.to_native_types(slicer=slicer,
                                           na_rep=na_rep,
                                           quoting=quoting,
                                           **kwargs) 

def hwc_mixed_005_02(data, output_folder, result_info_key, identifier_keys):
    """Creates CSV files containing data returned by the Analytics API.
       Creates one file per requested endpoint and saves it into the
       specified output_folder

    Args:
        data: Analytics API data as a list of dicts
        output_folder: Path to a folder to save the CSV files into
    """
    workbook = create_excel_workbook(data, result_info_key, identifier_keys)

    suffix = '.csv'

    if not os.path.exists(output_folder):
        os.makedirs(output_folder)

    for worksheet in workbook.worksheets:
        file_name = utilities.convert_title_to_snake_case(worksheet.title)

        file_path = os.path.join(output_folder, file_name + suffix)

        mode = 'w'
        if sys.version_info[0] < 3:
            mode = 'wb'
        with io.open(file_path, mode) as output_file:
            csv_writer = csv.writer(output_file)
            for row in worksheet.rows:
                csv_writer.writerow([cell.value for cell in row])

    print('Saved CSV files to {}'.format(output_folder)) 

def agc_mixed_005_03(env, target, source=None, *args, **kw):
    """
    A pseudo-Builder, applying a simple XSL transformation to the input file.
    """
    # Init list of targets/sources
    if source is None:
        source = target
    else:
        source = [source]
    source = [str(f) for f in source]
    target = str(target)
    xslt = kw.get('xslt', 'docbook-xsl')
    xsltproc = env.subst('$XSLTPROC')
    if not xsltproc:
        raise Utils.WafError('docbook-xsl: xsltproc not found')
    if not os.path.exists(xslt):
        raise Utils.WafError('docbook-xsl: %r not found' % xslt)
    if not os.path.exists(xsltproc):
        raise Utils.WafError('docbook-xsl: %r not found' % xsltproc)
    if not source:
        raise Utils.WafError('docbook-xsl: no input file')
    if not target:
        raise Utils.WafError('docbook-xsl: no output file')
    cmd = [xsltproc, xslt, '-o', target] + source
    env.Execute(cmd) 

def agc_mixed_005_04(self, manifest):
        """
        Add useful details to the manifest about this service
        so that it can be used in an application.

        :param manifest: An predix.admin.app.Manifest object
            instance that manages reading/writing manifest config
            for a cloud foundry app.
        """
        # Add this service to list of services
        manifest.add_service(self.name, self.plan)
        manifest.add_env_var(self.name, 'PREDIX_SERVICE_HOST', self.host)
        manifest.add_env_var(self.name, 'PREDIX_SERVICE_PORT', self.port)
        manifest.add_env_var(self.name, 'PREDIX_SERVICE_USERNAME', self.username)
        manifest.add_env_var(self.name, 'PREDIX_SERVICE_PASSWORD', self.password)
        manifest.add_env_var(self.name, 'PREDIX_SERVICE_CLIENT_ID', self.client_id)
        manifest.add_env_var(self.name, 'PREDIX_SERVICE_CLIENT_SECRET', self.client_secret)
        manifest.add_env_var(self.name, 'PREDIX_SERVICE_AUTH_URL', self.auth_url)
        manifest.add_env_var(self.name, 'PREDIX_SERVICE_TOKEN_URL', self.token_url)
        manifest.add_env_var(self.name, 'PREDIX_SERVICE_REDIRECT_URL', self.redirect_url)
        manifest.add_env_var(self.name, 'PREDIX_SERVICE_SCOPE', self.scope)
        manifest.add_env_var(self.name, 'PREDIX_SERVICE_AUTHORIZATION_CODE', self.authorization_code)
        manifest.add_env_var(self.name, 'PREDIX_SERVICE_ACCESS_TOKEN', self.access_token)
        manifest.add_env_var(self.name, 'PREDIX_SERVICE_REFRESH_TOKEN', self.refresh_token)
        manifest.add_env_var(self.name, 'PREDIX_SERVICE_EXPIRES_IN', self.expires_in)
        manifest.add_env_var(self.name, 'PREDIX_SERVICE_TOKEN_TYPE', self.token_type)
        manifest.add_ 

def hwc_mixed_005_05(p):
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

def hwc_mixed_005_06(keyword, feature, parent):
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
