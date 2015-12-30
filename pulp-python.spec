%{!?python_sitelib: %global python_sitelib %(%{__python} -c "from distutils.sysconfig import get_python_lib; print(get_python_lib())")}
%{!?python_sitearch: %global python_sitearch %(%{__python} -c "from distutils.sysconfig import get_python_lib; print(get_python_lib(1))")}

Name: pulp-python
Version: 1.1.0
Release: 0.1.alpha%{?dist}
Summary: Support for Python content in the Pulp platform
Group: Development/Languages
License: GPLv2
URL: https://github.com/pulp/pulp_python
Source0: https://fedorahosted.org/releases/p/u/%{name}/%{name}-%{version}.tar.gz
BuildRoot: %{_tmppath}/%{name}-%{version}-%{release}-root-%(%{__id_u} -n)
BuildArch:      noarch
BuildRequires:  python-setuptools

# This is the minimum platform version we require to function.
%define pulp_version 2.7

%description
Provides a collection of platform plugins and client extensions support for Python packages.


%prep
%setup -q


%build
pushd common
%{__python} setup.py build
popd

pushd extensions_admin
%{__python} setup.py build
popd

pushd plugins
%{__python} setup.py build
popd


%install
rm -rf %{buildroot}

mkdir -p %{buildroot}/%{_sysconfdir}/pulp/
mkdir -p %{buildroot}/%{_sysconfdir}/pulp/vhosts80/

pushd common
%{__python} setup.py install -O1 --skip-build --root %{buildroot}
popd

pushd extensions_admin
%{__python} setup.py install -O1 --skip-build --root %{buildroot}
popd

pushd plugins
%{__python} setup.py install -O1 --skip-build --root %{buildroot}
popd

mkdir -p %{buildroot}/%{_var}/lib/pulp/published/python

cp -R plugins/etc/httpd %{buildroot}/%{_sysconfdir}/
cp plugins/etc/pulp/vhosts80/pulp_python.conf %{buildroot}/%{_sysconfdir}/pulp/vhosts80/

# Remove tests
rm -rf %{buildroot}/%{python_sitelib}/test

%clean
rm -rf %{buildroot}


# ---- Common (check out the hilarious package name!)---------------------------
%package -n python-pulp-python-common
Summary: Pulp Python support common library
Group: Development/Languages
Requires: python-pulp-common >= %{pulp_version}
Requires: python-setuptools

%description -n python-pulp-python-common
A collection of modules shared among all Pulp-Python components.

%files -n python-pulp-python-common
%defattr(-,root,root,-)
%dir %{python_sitelib}/pulp_python
%{python_sitelib}/pulp_python/__init__.py*
%{python_sitelib}/pulp_python/common/
%dir %{python_sitelib}/pulp_python/extensions
%{python_sitelib}/pulp_python/extensions/__init__.py*
%{python_sitelib}/pulp_python_common*.egg-info
%doc COPYRIGHT LICENSE AUTHORS


# ---- Plugins -----------------------------------------------------------------
%package plugins
Summary: Pulp Python plugins
Group: Development/Languages
Requires: python-pulp-common >= %{pulp_version}
Requires: python-pulp-python-common >= %{version}
Requires: pulp-server >= %{pulp_version}
Requires: python-setuptools

%description plugins
Provides a collection of platform plugins that extend the Pulp platform
to provide Python package support.

%files plugins
%defattr(-,root,root,-)
%{python_sitelib}/pulp_python/plugins/
%config(noreplace) %{_sysconfdir}/httpd/conf.d/pulp_python.conf
%config(noreplace) %{_sysconfdir}/pulp/vhosts80/pulp_python.conf
%{python_sitelib}/pulp_python_plugins*.egg-info

%defattr(-,apache,apache,-)
%{_var}/lib/pulp/published/python/

%doc COPYRIGHT LICENSE AUTHORS


# ---- Admin Extensions --------------------------------------------------------
%package admin-extensions
Summary: The Python admin client extensions
Group: Development/Languages
Requires: python-pulp-common >= %{pulp_version}
Requires: python-pulp-python-common = %{version}
Requires: pulp-admin-client >= %{pulp_version}
Requires: python-setuptools

%description admin-extensions
A collection of extensions that supplement and override generic admin
client capabilites with Python specific features.

%files admin-extensions
%defattr(-,root,root,-)
%{python_sitelib}/pulp_python/extensions/admin/
%{python_sitelib}/pulp_python_extensions_admin*.egg-info
%doc COPYRIGHT LICENSE AUTHORS


%changelog
* Tue Mar 24 2015 Randy Barlow <rbarlow@redhat.com> 1.0.0-0.1.beta
- Added ability to synchronize with PyPI.

* Wed Jan 21 2015 Randy Barlow <rbarlow@redhat.com> 0.0.0-1
- Initial release
- Adding ability to remove Python packages from Pulp repository using pulp-
  admin (skarmark@redhat.com)
- Support copying Python packages between repos. (rbarlow@redhat.com)
- Add a CLI command to list packages. (rbarlow@redhat.com)
- Create documentation. (rbarlow@redhat.com)
