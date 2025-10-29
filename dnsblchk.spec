%global src_name dnsblchk

Name:           %{src_name}
Version:        @VERSION@
Release:        1%{?dist}
Summary:        A DNS Blacklist Checker service
License:        MIT
URL:            https://github.com/transilvlad/dnsblchk
Source0:        %{src_name}-%{version}.tar.gz
BuildArch:      noarch

BuildRequires:  python3
BuildRequires:  python3-pip
BuildRequires:  python3-setuptools

Requires:       python3
Requires:       python3-pip
Requires(post):   systemd
Requires(preun):  systemd
Requires(postun): systemd

%description
A service to monitor IP addresses against DNS blacklists (DNSBLs) and send email alerts.

%prep
%setup -q -n %{src_name}-%{version}

%build
# Pure Python; nothing to compile.

%install
pip3 install --no-cache-dir wheel || :
pip3 install --root %{buildroot} --no-deps .
install -d -m 755 %{buildroot}/%{_sysconfdir}/%{src_name}
install -d -m 755 %{buildroot}/%{_unitdir}
install -d -m 755 %{buildroot}/var/log/%{src_name}
install -d -m 755 %{buildroot}/var/run/%{src_name}
install -m 644 dnsblchk.service %{buildroot}/%{_unitdir}/dnsblchk.service
install -m 644 config/config.yaml.template %{buildroot}/%{_sysconfdir}/%{src_name}/config.yaml

%post
%systemd_post dnsblchk.service
/usr/sbin/useradd -r -s /bin/false -d /opt/%{src_name} %{src_name} >/dev/null 2>&1 || :
chown -R %{src_name}:%{src_name} /var/log/%{src_name}
chown -R %{src_name}:%{src_name} /var/run/%{src_name}
echo "Installation complete. Configure /etc/dnsblchk/config.yaml"
echo "Start: systemctl start dnsblchk.service"

%preun
%systemd_preun dnsblchk.service

%postun
%systemd_postun_with_restart dnsblchk.service
/usr/sbin/userdel %{src_name} >/dev/null 2>&1 || :

%files
%license LICENSE
%doc README.md
%{python3_sitelib}/config.py
%{python3_sitelib}/dnscheck.py
%{python3_sitelib}/files.py
%{python3_sitelib}/logger.py
%{python3_sitelib}/mail.py
%{python3_sitelib}/main.py
%{python3_sitelib}/rblcheck.py
%{python3_sitelib}/signals.py
%dir %{python3_sitelib}/__pycache__
%{python3_sitelib}/__pycache__/*.pyc
%{python3_sitelib}/dnsblchk-*.dist-info/*
%{_bindir}/dnsblchk
%config(noreplace) %{_sysconfdir}/%{src_name}/config.yaml
%{_unitdir}/dnsblchk.service
/var/log/%{src_name}
/var/run/%{src_name}
