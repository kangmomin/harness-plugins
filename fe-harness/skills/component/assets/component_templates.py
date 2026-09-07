#!/usr/bin/env python3
"""Emit framework/language/runner-specific scaffolding as JSON; never write files."""
import argparse
import json
import re
import sys


def templates(name, framework, typescript, runner, storybook=False, ui="tailwind"):
    if not re.fullmatch(r"[A-Z][A-Za-z0-9]{0,79}", name) or name in ("React", "Meta", "StoryObj"):
        raise ValueError("INVALID_NAME: use a nonreserved PascalCase component name")
    if type(typescript) is not bool or type(storybook) is not bool:
        raise ValueError("INVALID_LANGUAGE_FLAGS")
    vue = framework == "nuxt"
    if framework not in ("nextjs", "vite", "cra", "nuxt") or runner not in ("vitest", "jest"):
        raise ValueError("UNSUPPORTED_COMBINATION: inspect the project's own template before writing")
    if vue and runner == "jest":
        raise ValueError("UNSUPPORTED_COMBINATION: Vue/Jest SFC transforms are project-specific; provide a tested project template")
    if ui not in (("tailwind", "css-modules") if vue else ("tailwind", "css-modules", "styled-components", "shadcn", "mui", "antd")):
        raise ValueError("UNSUPPORTED_COMBINATION: UI library does not match framework")
    ext = "ts" if typescript else "js"
    component_ext = "vue" if vue else ext + "x"
    test_ext = ext if vue else component_ext
    files = {}
    if vue:
        lang = ' lang="ts"' if typescript else ""
        source = f'<script setup{lang}>\ndefineOptions({{ name: "{name}" }});\n</script>\n\n<template>\n  <section><slot /></section>\n</template>\n'
        if ui == "css-modules":
            source = source.replace("<section>", '<section :class="$style.root">')
            source += f'\n<style module src="./{name}.module.css"></style>\n'
        test_import = f"import {name} from './{name}.vue';"
        render = f"render({name}, {{ slots: {{ default: 'Supplied content' }} }});"
        export = f"export {{ default as {name} }} from './{name}.vue';\n"
    else:
        props = f"type {name}Props = {{ children?: React.ReactNode }};\n\n" if typescript else ""
        annotation = f": {name}Props" if typescript else ""
        source = f"import * as React from 'react';\n\n{props}export function {name}({{ children }}{annotation}) {{\n  return <section>{{children}}</section>;\n}}\n"
        if ui == "css-modules":
            source = f"import styles from './{name}.module.css';\n" + source.replace("<section>", "<section className={styles.root}>")
        if ui == "styled-components":
            source = f"import {{ Root }} from './{name}.styled';\n" + source.replace("<section>", "<Root>").replace("</section>", "</Root>")
            files[f"{name}.styled.{ext}"] = "import styled from 'styled-components';\n\nexport const Root = styled.section``;\n"
            if framework == "nextjs":
                source = "'use client';\n\n" + source
        test_import = f"import * as React from 'react';\nimport {{ {name} }} from './{name}';"
        render = f"render(<{name}>Supplied content</{name}>);"
        export = f"export {{ {name} }} from './{name}';\n"
    library = "vue" if vue else "react"
    runner_module = "vitest" if runner == "vitest" else "@jest/globals"
    files[f"{name}.{component_ext}"] = source
    files[f"{name}.test.{test_ext}"] = (
        f"import {{ afterEach, describe, expect, it }} from '{runner_module}';\n"
        f"import {{ cleanup, render, screen }} from '@testing-library/{library}';\n"
        f"{test_import}\n\nafterEach(cleanup);\n\ndescribe('{name}', () => {{\n"
        f"  it('renders supplied content', () => {{\n    {render}\n"
        "    expect(screen.getByText('Supplied content').textContent).toBe('Supplied content');\n  });\n});\n"
    )
    if ui == "css-modules":
        files[f"{name}.module.css"] = ".root {\n  display: block;\n}\n"
    if storybook:
        renderer = "vue3" if vue else "react"
        imports = f"import type {{ Meta, StoryObj }} from '@storybook/{renderer}';\n" if typescript else ""
        component_import = test_import.split("\n")[-1]
        meta_type = f": Meta<typeof {name}>" if typescript else ""
        story_type = "\ntype Story = StoryObj<typeof meta>;\n" if typescript else ""
        files[f"{name}.stories.{ext}"] = (
            f"{imports}{component_import}\n\nconst meta{meta_type} = {{\n  title: '{name}',\n  component: {name},\n}};\n\n"
            f"export default meta;\n{story_type}\nexport const Default{': Story' if typescript else ''} = {{}};\n"
        )
    files[f"index.{ext}"] = export
    return dict(framework=framework, typescript=typescript, runner=runner, files=files,
                prerequisites=["@testing-library/" + library, runner, "jsdom"] + (["@storybook/" + ("vue3" if vue else "react")] if storybook else []))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--name", required=True)
    p.add_argument("--framework", required=True)
    p.add_argument("--typescript", choices=("true", "false"), required=True)
    p.add_argument("--runner", required=True)
    p.add_argument("--storybook", action="store_true")
    p.add_argument("--ui", default="tailwind")
    args = p.parse_args()
    try:
        print(json.dumps(templates(args.name, args.framework, args.typescript == "true", args.runner, args.storybook, args.ui), ensure_ascii=False))
        return 0
    except ValueError as exc:
        print(json.dumps(dict(status="BLOCKED", error=str(exc))), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
