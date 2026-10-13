import React from 'react';
import { useTranslation } from 'react-i18next';
import { Globe, Check } from 'lucide-react';
import { Button } from '@/components/ui/button';
import {
  DropdownMenu,
  DropdownMenuTrigger,
  DropdownMenuContent,
  DropdownMenuItem,
} from '@/components/ui/dropdown-menu';
import { LANGUAGES } from '../../i18n';

export const LanguageSwitcher = () => {
  const { i18n } = useTranslation();
  const current = LANGUAGES.find((l) => i18n.language?.startsWith(l.code)) || LANGUAGES[0];

  // Some labels are picked once when their screen's module loads, so reload to show every label in the new language.
  const switchLanguage = (code) => {
    if (code === current.code) return;
    i18n.changeLanguage(code).then(() => window.location.reload());
  };

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button
          size="sm"
          variant="outline"
          className="bg-slate-800/80 backdrop-blur-sm border-slate-600 text-slate-200 hover:bg-slate-700 hover:text-white"
          data-testid="language-switcher-btn"
        >
          <Globe className="h-4 w-4 mr-1.5 text-lime" />
          {current.native}
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent
        align="end"
        className="bg-slate-900 border-slate-700 text-white max-h-80 overflow-y-auto z-[100]"
        data-testid="language-dropdown"
      >
        {LANGUAGES.map((lang) => (
          <DropdownMenuItem
            key={lang.code}
            onClick={() => switchLanguage(lang.code)}
            className="cursor-pointer focus:bg-slate-800 focus:text-white flex items-center gap-2"
            data-testid={`lang-option-${lang.code}`}
          >
            <span>{lang.native}</span>
            <span className="text-slate-500 text-xs">{lang.name}</span>
            {current.code === lang.code && <Check className="h-4 w-4 ml-auto text-lime" />}
          </DropdownMenuItem>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  );
};

export default LanguageSwitcher;
