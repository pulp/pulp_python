%{!?python_sitelib: %global python_sitelib %(%{__python} -c "from distutils.sysconfig import get_python_lib; print(get_python_lib())")}
%{!?python_sitearch: %global python_sitearch %(%{__python} -c "from distutils.sysconfig import get_python_lib; print(get_python_lib(1))")}

Name: pulp-python
Version: 2.0.1
Release: 0.1.beta%{?dist}
Summary: Support for Python content in the Pulp platform
Group: Development/Languages
License: GPLv2
URL: https://github.com/pulp/pulp_python
Source0: https://fedorahosted.org/releases/p/u/%{name}/%{name}-%{version}.tar.gz
BuildRoot: %{_tmppath}/%{name}-%{version}-%{release}-root-%(%{__id_u} -n)
BuildArch:      noarch
BuildRequires:  python-setuptools

# This is the minimum platform version we require to function.
%define pulp_version 2.11

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


%clean
rm -rf %{buildroot}


# ---- Common (check out the hilarious package name!)---------------------------
%package -n python-pulp-python-common
Summary: Pulp Python support common library
Group: Development/Languages
Provides: python2-pulp-python-common
Obsoletes: python2-pulp-python-common < %{version}
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
Requires: python-twine

%description plugins
Provides a collection of platform plugins that extend the Pulp platform
to provide Python package support.

%files plugins
%defattr(-,root,root,-)
%{python_sitelib}/pulp_python/plugins/
%config(noreplace) %{_sysconfdir}/httpd/conf.d/pulp_python.conf
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
* Thu Mar 03 2016 Dennis Kliban <dkliban@redhat.com> 1.1.0-0.4.beta
- Merge branch 'master' into 1.1.0 (dkliban@redhat.com)
- Bumping version to 1.1.0-0.4.beta (dkliban@redhat.com)
- Configure Travis to only flake8 and pep257 the code. (rbarlow@redhat.com)
- Merge branch 'test_proxy_true' (rbarlow@redhat.com)
- Add a test to ensure that proxies are available for Python.
  (rbarlow@redhat.com)
- Merge pull request #66 from dkliban/check-unique-2 (dkliban@redhat.com)
- Adds check for duplicate unit key (dkliban@redhat.com)
- Use a Python 2.6 friendly string format syntax. (rbarlow@redhat.com)
- Merge pull request #65 from seandst/413 (sean.myers@redhat.com)
- Block attempts to load server.conf when running tests (sean.myers@redhat.com)
- Enable proxy support in pulp_python by default (JohnsonAaron@JohnDeere.com)

* Wed Mar 02 2016 Dennis Kliban <dkliban@redhat.com> 1.1.0-0.3.beta
- Bumping version to 1.1.0-0.3.beta (dkliban@redhat.com)

* Fri Feb 19 2016 Dennis Kliban <dkliban@redhat.com> 1.1.0-0.2.beta
- This uniqueness contstraint is now enforced by the platform for all content
  units. (dkliban@redhat.com)
- Do not install plugin tests. (rbarlow@redhat.com)
- Do not package tests. (rbarlow@redhat.com)
- Fix broken http config (pcreech@redhat.com)
- Merge branch 'rm_empty_conf' (rbarlow@redhat.com)
- Merge branch 'rm_empty_errors' (rbarlow@redhat.com)
- Bumping version to 1.1.0-0.2.beta (dkliban@redhat.com)
- Now that #293 is fixed, we don't need this empty config. (rbarlow@redhat.com)
- Remove an empty and unused errors.py. (rbarlow@redhat.com)

* Thu Jan 28 2016 Dennis Kliban <dkliban@redhat.com> 1.1.0-0.1.alpha
- Ensure file objects are cleaned up on error (pcreech@redhat.com)
- converted to use mongoengine (mhrivnak@redhat.com)
- Convert shebang to python2 (ipanova@redhat.com)
- Merge branch '1.0-dev' (dkliban@redhat.com)
- Adds fc23 to dist_list.txt config and removes fc21. (dkliban@redhat.com)
- Merge branch 'pr/51' (ipanova@redhat.com)
- 1349 - Handles repo.working_dir None (vjancik@redhat.com)
- Merge branch '1.0-dev' (ipanova@redhat.com)
- Merge branch '1.0-testing' into 1.0-dev (ipanova@redhat.com)
- Merge branch '1.0-release' into 1.0-testing (ipanova@redhat.com)
- Adjusting documentation for the package_names config key.
  (ipanova@redhat.com)
- Limit Mock to <1.1 in test_requirement.txt. (rbarlow@redhat.com)
- Don't test pulp_python against pypi in Travis. (rbarlow@redhat.com)
- Ignore D104 in our pep257 checks. (rbarlow@redhat.com)
- Merge branch '1.0-dev' (ipanova@redhat.com)
- Enable auto-publish by default. (ipanova@redhat.com)
- Merge branch '1.0-dev' (ipanova@redhat.com)
- Merge branch '1.0-testing' into 1.0-dev (ipanova@redhat.com)
- Removing shutil.move and copytree where /var/cache/pulp is involved
  (ipanova@redhat.com)
- Automatic commit of package [pulp-python] release [1.0.1-1]. (pulp-
  infra@redhat.com)
- Bumping version for 1.0.1 release (dkliban@redhat.com)
- Automatic commit of package [pulp-python] release [1.0.1-0.2.rc]. (pulp-
  infra@redhat.com)
- Bumping version for 1.0.1 RC1 (dkliban@redhat.com)
- Automatic commit of package [pulp-python] release [1.0.1-0.1.beta]. (pulp-
  infra@redhat.com)
- Bumping build number for 1.0.1 beta (dkliban@redhat.com)
- Merge branch '1.0-dev' (dkliban@redhat.com)
- Merge branch '1.0-testing' into 1.0-dev (dkliban@redhat.com)
- Removed fc20 from dist_list.txt (dkliban@redhat.com)
- Merge branch '1.0-dev' (dkliban@redhat.com)
- Merge branch '1.0-testing' into 1.0-dev (dkliban@redhat.com)
- Added fc22 to dist_list.txt (dkliban@redhat.com)
- Merge branch '1.0-dev' (rbarlow@redhat.com)
- Merge branch '1.0-testing' into 1.0-dev (rbarlow@redhat.com)
- Add Graham Forest to the AUTHORS file. (rbarlow@redhat.com)
- Merge branch '1.0-dev' (rbarlow@redhat.com)
- Merge branch '1.0-testing' into 1.0-dev (rbarlow@redhat.com)
- Add release notes for 1.0.1. (rbarlow@redhat.com)
- Automatic commit of package [pulp-python] release [1.0.1-0.0.beta]. (pulp-
  infra@redhat.com)
- Set the version to 1.0.2-0.0.alpha. (rbarlow@redhat.com)
- Set the version to 1.0.1-0.0.beta. (rbarlow@redhat.com)
- Use the PKG-INFO file with the shortest path (graham@urbanairship.com)
- Add DOS line ending support (graham@urbanairship.com)
- Add nosexcover to test_requirements.txt. (rbarlow@redhat.com)
- Merge pull request #40 from urbanairship/dos-line-ending-support
  (rbarlow@redhat.com)
- Modify test requirements. (rbarlow@redhat.com)
- Use the PKG-INFO file with the shortest path (graham@urbanairship.com)
- Add DOS line ending support (graham@urbanairship.com)
- Bump the version requirement & the base version of pulp-python
  (bcourt@redhat.com)
- Rename .rst (ryan@ryanhiebert.com)
- Fix import ordering (cduryee@redhat.com)
- re-apply 2.7 specific changes (bcourt@redhat.com)
- Update the .travis.yml & run-tests to maintain Pulp 2.6 Compatibility Fix
  .travis.yaml to not use the --cover-min-percentage flag which is not
  available in 2.6.0 Put back the line in the .travis.yaml to load okaara,
  pymongo, and iniparse Add mongoengine to the .travis.yml file
  (bcourt@redhat.com)
- Merge branch '1.0-release' into 1.0-testing (bcourt@redhat.com)
- Set the version to 1.0.0-1. (rbarlow@redhat.com)
- Merge branch '1.0-dev' (bmbouter@gmail.com)
- Merge branch '1.0-testing' into 1.0-dev (bmbouter@gmail.com)
- Adds exlinks references, and adds a Bugs release note for 1.0.0
  (bmbouter@gmail.com)
- Automatic commit of package [pulp-python] release [1.0.0-0.3.rc]. (pulp-
  infra@redhat.com)
- Merge remote-tracking branch 'origin/1.0-dev' (cduryee@redhat.com)
- Merge remote-tracking branch 'origin/1.0-testing' into 1.0-dev
  (cduryee@redhat.com)
- Merge pull request #34 from rbarlow/rc2 (cduryee@redhat.com)
- Set the version to 1.0.0-0.3.rc. (rbarlow@redhat.com)
- Add an empty /etc/pulp/vhosts80/pulp_python.conf. (rbarlow@redhat.com)
- Automatic commit of package [pulp-python] release [1.0.0-0.2.rc]. (pulp-
  infra@redhat.com)
- Merge branch '1.0-dev' (rbarlow@redhat.com)
- Merge branch 'rc' into 1.0-testing (rbarlow@redhat.com)
- Merge branch '1.0-dev' (rbarlow@redhat.com)
- Set the version to 1.0.0-0.2.rc. (rbarlow@redhat.com)
- Ensure that documented examples use correct package names.
  (rbarlow@redhat.com)
- Merge branch '1.0-dev' (rbarlow@redhat.com)
- Merge branch '1.0-dev' (rbarlow@redhat.com)
- Merge branch '1.0-dev' (rbarlow@redhat.com)
- Merge branch '1.0-dev' (rbarlow@redhat.com)

* Tue Mar 24 2015 Randy Barlow <rbarlow@redhat.com> 1.0.0-0.1.beta
- Added ability to synchronize with PyPI.

* Wed Jan 21 2015 Randy Barlow <rbarlow@redhat.com> 0.0.0-1
- Initial release
- Adding ability to remove Python packages from Pulp repository using pulp-
  admin (skarmark@redhat.com)
- Support copying Python packages between repos. (rbarlow@redhat.com)
- Add a CLI command to list packages. (rbarlow@redhat.com)
- Create documentation. (rbarlow@redhat.com)
