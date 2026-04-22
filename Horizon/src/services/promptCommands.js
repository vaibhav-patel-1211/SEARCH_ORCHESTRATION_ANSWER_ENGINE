export const toPromptCommandKey = (name = '') =>
  String(name)
    .trim()
    .replace(/\s+/g, '_')
    .replace(/[^a-zA-Z0-9_]/g, '')
    .toUpperCase()

export const PROMPT_COMMAND_ARGUMENT_PLACEHOLDER = 'Topic_name that will use in this prompt'

export const buildPromptCommand = (
  name,
  argumentPlaceholder = PROMPT_COMMAND_ARGUMENT_PLACEHOLDER,
) => {
  const key = toPromptCommandKey(name)
  if (!key) return ''
  return `/${key}:[${argumentPlaceholder}]`
}

const COMMAND_REGEX = /\/([a-zA-Z0-9_]+):\[(.*?)\]/g
const PLACEHOLDER_REGEX = /\[([A-Z][A-Z0-9_]{1,49})\]/g

export const expandPromptCommands = (input, savedPrompts = []) => {
  if (typeof input !== 'string' || !input) return input ?? ''

  const promptByCommand = new Map()
  for (const prompt of savedPrompts) {
    const content = typeof prompt?.content === 'string' ? prompt.content : ''
    if (!content) continue

    const commandKey = toPromptCommandKey(prompt?.name)
    if (commandKey) promptByCommand.set(commandKey, content)
  }

  return input.replace(COMMAND_REGEX, (match, rawCommand, rawArgument) => {
    const command = String(rawCommand || '').trim().toUpperCase()
    const template = promptByCommand.get(command)
    if (!template) return match

    const argument = String(rawArgument || '').trim()
    if (!argument) return template

    return template.replace(PLACEHOLDER_REGEX, argument)
  })
}
