#!/usr/bin/env python3

from json import loads as json_loads
from requests import get
from pathlib import Path
from shutil import copy as copy_file
from subprocess import run


# dependency modifier
def add_depends(package_dir: str, package_name: str, depends) -> None:
    """Add dependencies to a package

    Args:
        package_dir (str): a directory where package sources are located
        package_name (str): a name of package
        depends (list[str]): a list of dependencies to add
    """
    depends_list: str = ', '.join(depends)
    depends_line: str = f'misc:Depends={depends_list}\n'

    substvars_file = Path(f'{package_dir}/debian/{package_name}.substvars')
    substvars_file.write_text(depends_line)


# copy patches
def apply_deb_patches(package_name: str, sources_dir: str):
    """Apply patches to sources directory

    Args:
        package_name (str): package name
        sources_dir (str): sources dir
    """
    patches_dir = Path(f'patches/{package_name}')
    if patches_dir.exists():
        patches_list = list(patches_dir.iterdir())
        patches_list.sort()
        series_file = Path(f'{sources_dir}/debian/patches/series')
        series_data = ''
        for patch_file in patches_list:
            print(f'Applying patch: {patch_file.name}')
            copy_file(patch_file, f'{sources_dir}/debian/patches/')
            if series_file.exists():
                series_data = series_file.read_text()
            series_data = f'{series_data}\n{patch_file.name}'
            series_file.write_text(series_data)


# find kernel version and source path
defaults_file: str = Path('../../data/defaults.json').read_text()
KERNEL_VER: str = json_loads(defaults_file).get('kernel_version')
KERNEL_FLAVOR: str = json_loads(defaults_file).get('kernel_flavor')
KERNEL_SRC: str = Path.cwd().as_posix() + '/linux'

# define variables
PACKAGE_NAME: str = 'vyos-drivers-realtek-r8168'
PACKAGE_VERSION: str = '8.052.01'
PACKAGE_DIR: str = f'{PACKAGE_NAME}-{PACKAGE_VERSION}'
SOURCES_ARCHIVE: str = 'r8168-2.17.1.tar.gz'
SOURCES_URL: str = f'https://github.com/mtorromeo/r8168/archive/refs/tags/{PACKAGE_VERSION}.tar.gz'

# download sources
sources_archive = Path(SOURCES_ARCHIVE)
sources_archive.write_bytes(get(SOURCES_URL).content)

# prepare sources
debmake_cmd = [
    'debmake', '-e', 'support@vyos.io', '-f', 'VyOS Support', '-p',
    PACKAGE_NAME, '-u', PACKAGE_VERSION, '-a', SOURCES_ARCHIVE
]
run(debmake_cmd)

# add kernel to dependencies
add_depends(PACKAGE_DIR, PACKAGE_NAME,
            [f'linux-image-{KERNEL_VER}-{KERNEL_FLAVOR}'])

# configure build rules
build_rules_text: str = f'''#!/usr/bin/make -f
# config
export KERNELDIR := {KERNEL_SRC}
PACKAGE_BUILD_DIR := debian/{PACKAGE_NAME}
KVER := {KERNEL_VER}-{KERNEL_FLAVOR}
MODULES_DIR := updates/drivers/net/usb

# main packaging script based on dh7 syntax
%:
	dh $@  

override_dh_clean:
	dh_clean --exclude=debian/{PACKAGE_NAME}.substvars

override_dh_prep:
	dh_prep --exclude=debian/{PACKAGE_NAME}.substvars

override_dh_auto_clean:
	make clean

override_dh_auto_build:
	make modules

override_dh_auto_install:
	install -D -m 644 src/r8168.ko ${{PACKAGE_BUILD_DIR}}/lib/modules/${{KVER}}/${{MODULES_DIR}}/r8168.ko
	install -D -m 644 modprobe-r8168.conf ${{PACKAGE_BUILD_DIR}}/etc/modprobe.d/r8168.conf
'''
bild_rules = Path(f'{PACKAGE_DIR}/debian/rules')
bild_rules.write_text(build_rules_text)

# apply patches
apply_deb_patches(PACKAGE_NAME, PACKAGE_DIR)

# build a package
debuild_cmd = ['debuild']
run(debuild_cmd, cwd=PACKAGE_DIR)
