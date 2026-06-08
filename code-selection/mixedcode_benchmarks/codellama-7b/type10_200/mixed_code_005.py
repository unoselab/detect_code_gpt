def agc_mixed_005_01(self, cmd="sudo su", pattern="ssword", re_flags=re.IGNORECASE):
        """Attempt to become root."""
        if self.is_root():
            return True
        if not self.is_root():
            self.log.info("Attempting to become root.")
            self.sendline(cmd)
            self.expect(pattern, timeout=10)
            self.sendline(self.password)
            self.expect(self.prompt)
            if self.is_root():
                self.log.info("Successfully became root.")
                return True
            else:
                self.log.error("Failed to become root.")
                return False 

def hwc_mixed_005_02(instance):
    """Ensure cyber observable timestamp properties with a comparison
    requirement are valid.
    """
    for key, obj in instance['objects'].items():
        compares = enums.TIMESTAMP_COMPARE_OBSERVABLE.get(obj.get('type', ''), [])
        print(compares)
        for first, op, second in compares:
            comp = getattr(operator, op)
            comp_str = get_comparison_string(op)

            if first in obj and second in obj and \
                    not comp(obj[first], obj[second]):
                msg = "In object '%s', '%s' (%s) must be %s '%s' (%s)"
                yield JSONError(msg % (key, first, obj[first], comp_str, second, obj[second]),
                                instance['id']) 

def agc_mixed_005_03(self, node):
        """
        Initialise aliasing default value before visiting.

        Add aliasing values for :
            - Pythonic
            - globals declarations
            - current function arguments
        """
        self.aliasing_default_value = {}
        self.aliasing_default_value.update(self.pythonic_aliasing_default_value)
        self.aliasing_default_value.update(self.globals_aliasing_default_value)
        self.aliasing_default_value.update(self.current_function_arguments_aliasing_default_value)

        self.current_function_arguments_aliasing_default_value = {}
        self.current_function_arguments_aliasing_default_value.update(self.aliasing_default_value)

        self.aliasing_default_value.update(self.current_function_aliasing_default_value)

        self.current_function_aliasing_default_value = {}
        self.current_function_aliasing_default_value.update(self.aliasing_default_value)

        self.aliasing_default_value.update(self.current_function_return_aliasing_default_value)

        self.current_function_return_aliasing_default_value = {}
        self.current_function_return_aliasing_default_value.update(self.aliasing_default_value)

        self.aliasing_default_value.update(self.current_function_arguments_aliasing_default_value)

        self.current_function_arguments_aliasing_default_value = {}
        self.current_function_arguments_aliasing_default_value.update(self.aliasing_default_value)

        self.aliasing_default_value.update(self.current_function_aliasing_default_value)

        self.current_function_aliasing_default_value = {}
        self.current_function_aliasing_default_value.update(self.aliasing_default_value)

        self.aliasing_default_value.update(self.current_function_return_aliasing_default_value)

        self.current_function_return_aliasing_default_value = {}
        self.current_function_return_aliasing_default_value.update(self.aliasing_default_value)

        self.aliasing 

def agc_mixed_005_04(self):
        """Check if the RPM Python binding has a depndency to popt-devel.

        Search include header files in the source code to check it.
        """
        if self.rpm_py_has_popt_devel_dep is not None:
            return self.rpm_py_has_popt_devel_dep

        self.rpm_py_has_popt_devel_dep = False
        for f in self.rpm_py_files:
            if f.endswith('.h'):
                with open(f, 'r') as fd:
                    for line in fd:
                        if 'popt.h' in line:
                            self.rpm_py_has_popt_devel_dep = True
                            break
        return self.rpm_py_has_popt_devel_dep 

def hwc_mixed_005_05(self, authorizer_name, authorizer_lambda_function_arn):
        """Constructs and returns the Lambda Permission resource allowing the Authorizer to invoke the function.

        :returns: the permission resource
        :rtype: model.lambda_.LambdaPermission
        """
        rest_api = ApiGatewayRestApi(self.logical_id, depends_on=self.depends_on, attributes=self.resource_attributes)
        api_id = rest_api.get_runtime_attr('rest_api_id')

        partition = ArnGenerator.get_partition_name()
        resource = '${__ApiId__}/authorizers/*'
        source_arn = fnSub(ArnGenerator.generate_arn(partition=partition, service='execute-api', resource=resource),
                           {"__ApiId__": api_id})

        lambda_permission = LambdaPermission(self.logical_id + authorizer_name + 'AuthorizerPermission',
                                             attributes=self.passthrough_resource_attributes)
        lambda_permission.Action = 'lambda:invokeFunction'
        lambda_permission.FunctionName = authorizer_lambda_function_arn
        lambda_permission.Principal = 'apigateway.amazonaws.com'
        lambda_permission.SourceArn = source_arn

        return lambda_permission 

def hwc_mixed_005_06(self):
        """Provides a name for display purpose"""
        displayName = self.name + "("
        if self.isAsync:
            displayName = "async " + displayName
        first = True
        for arg in self.arguments:
            if first:
                displayName += str(arg)
                first = False
            else:
                displayName += ", " + str(arg)
        displayName += ")"
        if self.returnAnnotation is not None:
            displayName += ' -> ' + self.returnAnnotation
        return displayName
